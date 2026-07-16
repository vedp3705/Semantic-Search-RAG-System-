from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
import config
import re

MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}
_DATE_RE    = re.compile(r'(\d{1,2})([A-Za-z]{3,9})(\d{4})', re.IGNORECASE)
_DATE_ISO   = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_TEACHER_RE = re.compile(r'_([A-Z]{2})(?:_|$)')


def get_box_client() -> BoxClient:
    auth = BoxDeveloperTokenAuth(token=config.BOX_ACCESS_TOKEN)
    return BoxClient(auth)


def _parse_date(name: str) -> str:
    m = _DATE_RE.search(name)
    if m:
        day = m.group(1).zfill(2)
        mon = MONTH_MAP.get(m.group(2).lower()[:3], '00')
        return f'{m.group(3)}-{mon}-{day}'
    m2 = _DATE_ISO.search(name)
    if m2:
        return m2.group(0)
    return 'unknown'


def _parse_teacher(name: str) -> str:
    matches = _TEACHER_RE.findall(name)
    return matches[0] if matches else 'unknown'


def _sanitize_id(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', name).strip('_')


def _files_from_items(items, folder_label: str) -> tuple[list, list]:
    """Split Box folder items into (docx_files, xlsx_files)."""
    docx, xlsx = [], []
    for item in items:
        if item.type != 'file':
            continue
        nl = item.name.lower()
        entry = {'id': item.id, 'name': item.name}
        if nl.endswith('.docx'):
            docx.append(entry)
        elif nl.endswith('.xlsx') or nl.endswith('.xls'):
            xlsx.append(entry)
    return docx, xlsx


def _get_data_folder_id(root_folder_id: str) -> str:
    client = get_box_client()
    items = client.folders.get_folder_items(folder_id=root_folder_id, limit=200)
    for item in items.entries:
        if item.type == 'folder' and item.name == 'Data':
            return item.id
    raise FileNotFoundError("'Data' folder not found inside the configured Box folder")


def list_sessions(root_folder_id: str) -> list[dict]:
    client = get_box_client()
    data_folder_id = _get_data_folder_id(root_folder_id)

    data_items = client.folders.get_folder_items(folder_id=data_folder_id, limit=200)
    entries = list(data_items.entries)

    subfolders = [e for e in entries if e.type == 'folder']

    if subfolders:
        sessions = []
        for folder in subfolders:
            name = folder.name
            sub_items = client.folders.get_folder_items(
                folder_id=folder.id, limit=200
            )
            docx, xlsx = _files_from_items(sub_items.entries, name)

            if not docx:
                print(f"  [skip] {name}/ — no .docx found")
                continue

            sessions.append({
                'session_id':   _sanitize_id(name),
                'lesson_date':  _parse_date(name),
                'teacher_code': _parse_teacher(name),
                'docx_files':   docx,
                'xlsx_files':   xlsx,
            })
        return sessions

    docx, xlsx = _files_from_items(entries, 'Data')
    if not docx:
        raise FileNotFoundError("No .docx files found in the Data folder")

    return [{
        'session_id':   config.BOX_TRANSCRIPT_ID,
        'lesson_date':  config.BOX_LESSON_DATE,
        'teacher_code': config.BOX_TEACHER_CODE,
        'docx_files':   docx,
        'xlsx_files':   xlsx,
    }]


def fetch_file_bytes(file_id: str) -> bytes:
    client = get_box_client()
    content = client.downloads.download_file(file_id=file_id)
    return content.read()
