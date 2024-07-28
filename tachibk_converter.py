import gzip
import re
import varint
from argparse import ArgumentParser
from base64 import b64decode, b64encode
from json import dumps, loads
from pathlib import Path
from requests import get
from struct import pack, unpack
from subprocess import run
from google.protobuf.json_format import (
    Parse,
    ParseError,
    MessageToDict,
)

FORKS = {
    'mihon': 'mihonapp/mihon',
    'sy': 'jobobby04/TachiyomiSY',
    'j2k': 'Jays2Kings/tachiyomiJ2K',
}

PROTONUMBER_RE = r'(?:^\s*(?!\/\/\s*)@ProtoNumber\((?P<number>\d+)\)\s*|data class \w+\(|^)va[rl]\s+(?P<name>\w+):\s+(?:(?:(?:List|Set)<(?P<list>\w+)>)|(?P<type>\w+))(?P<optional>\?|(:?\s+=))?'
CLASS_RE = r'^(?:data )?class (?P<name>\w+)\((?P<defs>(?:[^)(]+|\((?:[^)(]+|\([^)(]*\))*\))*)\)'
DATA_TYPES = {
    'String': 'string',
    'Int': 'int32',
    'Long': 'int64',
    'Boolean': 'bool',
    'Float': 'float',
}

argp = ArgumentParser()
argp.add_argument(
    '--input',
    '-i',
    metavar='<backup_file.tachibk | backup_file.proto.gz | decoded_backup.json>',
    help='File extension defines whether to decode a backup file to JSON or encode it back',
    type=Path,
)
argp.add_argument(
    '--output',
    '-o',
    default='output.json',
    metavar='<output.json | encoded_backup.tachibk>',
    help='When encoding, TACHIBK or PROTO.GZ will additionally recompress the backup file',
    type=Path,
)
argp.add_argument(
    '--fork',
    default=list(FORKS.keys())[0],
    choices=FORKS.keys(),
    metavar=f'<{" | ".join(FORKS.keys())}>',
    help='Fork for the backup schema. Default: mihon',
)
argp.add_argument(
    '--dump-schemas',
    action='store_true',
    help='Dump protobuf schemas from all supported forks',
)
argp.add_argument(
    '--convert-preferences',
    action='store_true',
    help='Convert the preference values into human-readable format.\n[EXPERIMENTAL!] May not be encoded back into a backup file',
)
args = argp.parse_args()


def fetch_schema(fork: str) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    git = get(
        f'https://api.github.com/repos/{fork}/contents/app/src/main/java/eu/kanade/tachiyomi/data/backup/models'
    ).json()
    for entry in git:
        if entry.get('type') == 'file':
            files.append((entry.get('name'), entry.get('download_url')))
        elif entry.get('type') == 'dir':
            for sub_entry in get(entry.get('url')).json():
                if sub_entry.get('type') == 'file':
                    files.append((sub_entry.get('name'), sub_entry.get('download_url')))
    return files


def parse_model(model: str) -> list[str]:
    data = get(model).text
    message: list[str] = []
    for name in re.finditer(CLASS_RE, data, re.MULTILINE):
        message.append('message {name} {{'.format(name=name.group('name')))
        for field in re.finditer(PROTONUMBER_RE, name.group('defs'), re.MULTILINE):
            message.append(
                '  {repeated} {type} {name} = {number};'.format(
                    repeated='repeated'
                    if field.group('list')
                    else 'optional'
                    if field.group('optional')
                    else 'required',
                    type=DATA_TYPES.get(
                        field.group('type'),
                        DATA_TYPES.get(
                            field.group('list'),
                            field.group('list') or field.group('type'),
                        ),
                    ),
                    name=field.group('name'),
                    number=field.group('number') or 1
                    if not name.group('name').startswith('Broken')
                    else int(field.group('number')) + 1,
                )
            )
        message.append('}\n')
    return message


def proto_gen(file: str = None, fork: str = args.fork):
    # Hard-coded exceptions to make parsing easier
    schema = '''syntax = "proto2";

enum UpdateStrategy {
  ALWAYS_UPDATE = 0;
  ONLY_FETCH_ONCE = 1;
}

message PreferenceValue {
  required string type = 1;
  required bytes truevalue = 2;
}

'''.splitlines()
    print(f'... Fetching from {fork.upper()}')
    for i in fetch_schema(FORKS[fork]):
        print(f'... Parsing {i[0]}')
        schema.append(f'// {i[0]}')
        schema.extend(parse_model(i[1]))
    filename = file or f'schema-{fork}.proto'
    print(f'Writing {filename}')
    print('\n'.join(schema), file=open(filename, 'wt'))


if args.dump_schemas:
    print('Generating Protobuf schemas')
    for fork in FORKS:
        proto_gen(fork=fork)
    print('END')
    exit(0)

try:
    from schema_pb2 import Backup
except (ModuleNotFoundError, NameError):
    print('No protobuf schema found...')
    proto_gen('schema.proto')
    print('Generating Python sources...')
    try:
        run(['protoc', '--python_out=.', '--pyi_out=.', 'schema.proto'])
    except FileNotFoundError:
        print(
            'ERROR! Protoc not found.',
            'Download at https://github.com/protocolbuffers/protobuf/releases/latest',
        )
        exit(1)
    try:
        from schema_pb2 import Backup
    except (ModuleNotFoundError, NameError):
        print('ERROR! Still unable to find the protobuf schema. Aborting.')
        exit(1)


def read_backup(input: str) -> str | bytes:
    if input.endswith('.tachibk') or input.endswith('.proto.gz'):
        with gzip.open(input, 'rb') as zip:
            backup_data = zip.read()
            with open('extracted_tachibk', 'wb') as file:
                file.write(backup_data)
    else:
        try:
            with open('extracted_tachibk', 'rb') as file:
                backup_data = file.read()
        except OSError:
            print('ERROR! No Backup to process.')
            argp.print_help()
            exit(1)
    return backup_data


def parse_backup(backup_data) -> Backup:
    message = Backup()
    message.ParseFromString(backup_data)
    return message


def write_json(message: Backup) -> None:
    message_dict = MessageToDict(message)

    if args.convert_preferences:
        print('Translating Preferences...')
        for idx, pref in enumerate(message_dict.get('backupPreferences')):
            message_dict['backupPreferences'][idx]['value']['truevalue'] = readable_preference(pref)
        for source_index, source in enumerate(message_dict.get('backupSourcePreferences')):
            for idx, pref in enumerate(source.get('prefs')):
                message_dict['backupSourcePreferences'][source_index]['prefs'][idx]['value'][
                    'truevalue'
                ] = readable_preference(pref)

    with open(args.output, 'wt') as file:
        file.write(dumps(message_dict, indent=2))
    print(f'Backup decoded to "{args.output}"')


def readable_preference(preference_value: dict):
    true_value = preference_value['value']['truevalue']
    match preference_value['value']['type'].split('.')[-1].removesuffix('PreferenceValue'):
        case 'Boolean':
            return bool(varint.decode_bytes(b64decode(true_value)[1:]))
        case 'Int' | 'Long':
            return varint.decode_bytes(b64decode(true_value)[1:])
        case 'Float':
            return unpack(
                'f',
                b64decode(true_value)[1:],
            )[0]
        case 'String':
            return b64decode(true_value)[2:].decode('utf-8')
        case 'StringSet':
            bar = list(b64decode(true_value))
            new_list = []
            for byte in bar:
                if byte == bar[0]:
                    new_list.append([])
                    continue
                new_list[-1].append(byte)
            for index, entry in enumerate(new_list):
                new_list[index] = bytes(entry[1:]).decode('utf-8')
            return new_list
        case _:
            return None


def bytes_preference(preference_value: dict) -> str:
    true_value = preference_value['value']['truevalue']
    print(f'Parsing {true_value}')
    
    value_type = preference_value['value']['type'].split('.')[-1].removesuffix('PreferenceValue')
    
    try:
        if value_type == 'Boolean':
            # Convert boolean to byte
            return b64encode(b'\x08' + (int(true_value) & 1).to_bytes(1, 'big')).decode()
        elif value_type in ('Int', 'Long'):
            # Convert integer to variable-length bytes
            return b64encode(b'\x08' + varint.encode(int(true_value))).decode()
        elif value_type == 'Float':
            # Convert float to bytes using 'struct' and pack it
            return b64encode(b'\r' + pack('f', float(true_value))).decode()
        elif value_type == 'String':
            # Convert string to bytes with length prefix
            true_value_bytes = true_value.encode()
            length_bytes = len(true_value_bytes).to_bytes(2, 'big')
            return b64encode(b'\n' + length_bytes + true_value_bytes).decode()
        elif value_type == 'StringSet':
            # Convert set of strings to bytes
            new_bytes = b''
            for val in true_value:
                val_bytes = val.encode()
                length_bytes = len(val_bytes).to_bytes(2, 'big')
                new_bytes += b'\n' + length_bytes + val_bytes
            return b64encode(new_bytes).decode()
        else:
            return ''
    except Exception as e:
        print(f'Error encoding preference: {e}')
        return ''



def parse_json(input: str) -> bytes:
    try:
        with open(input, 'r') as file:
            message_dict = loads(file.read())
    except OSError:
        print('ERROR! Could not read the JSON file.')
        exit(1)

    # Check if --convert-preferences was used
    for idx, pref in enumerate(message_dict.get('backupPreferences')):
        if 'String' not in pref['value']['type'] and isinstance(pref['value']['truevalue'], str):
            break
        message_dict['backupPreferences'][idx]['value']['truevalue'] = bytes_preference(pref)
    for source_index, source in enumerate(message_dict.get('backupSourcePreferences')):
        if source.get('prefs', "none") == "none":
            pass
        else:
            for idx, pref in enumerate(source.get('prefs')):
                if 'String' not in pref['value']['type'] and isinstance(
                    pref['value']['truevalue'], str
                ):
                    break
                message_dict['backupSourcePreferences'][source_index]['prefs'][idx]['value'][
                    'truevalue'
                ] = bytes_preference(pref)

    try:
        return Parse(dumps(message_dict), Backup()).SerializeToString()
    except ParseError as e:
        print('The input JSON file is invalid.', e)
        exit(1)


def write_backup(message: bytes) -> None:
    compression = True
    output = 'encoded_backup.tachibk' if str(args.output) == 'output.json' else str(args.output)
    if output.endswith('.proto.gz') or output.endswith('.tachibk'):
        with gzip.open(output, 'wb') as zip:
            zip.write(message)
    else:
        with open(output, 'wb') as file:
            file.write(message)
        compression = False
    print(f'{"C" if compression else "Unc"}ompressed backup written to {output}')


if __name__ == '__main__':
    input = str(args.input)
    if input.endswith('.json'):
        write_backup(parse_json(input))
    else:
        write_json(parse_backup(read_backup(input)))
# python tachibk-converter.py --input data.json backup.tachibk --output data.json