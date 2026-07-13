from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ProgressReporter = Callable[[str], None]


@dataclass(frozen=True)
class DriveFileInfo:
    id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    checksum: str | None = None
    parent_id: str | None = None
    drive_path: str | None = None


class DriveClient:
    """Interface for Google Drive file discovery and download."""

    def list_files(
        self,
        folder_id: str,
        mime_types: list[str],
        extensions: list[str],
        excluded_folder_name_contains: list[str],
        excluded_folder_names: list[str],
        recursive: bool,
        max_files: int | None = None,
        progress: ProgressReporter | None = None,
    ) -> list[DriveFileInfo]:
        raise NotImplementedError

    def download_file(self, file_id: str, destination: Path) -> Path:
        raise NotImplementedError


class GoogleDriveClient(DriveClient):
    """Google Drive API client using a service account credentials file."""

    def __init__(self, service_account_file: Path, include_shared_drives: bool = True) -> None:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:
            message = (
                "Google Drive dependencies are missing. Install with "
                "`pip install -e .[google]` before running Drive sync."
            )
            raise RuntimeError(message) from exc

        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=scopes,
        )
        self._service = build("drive", "v3", credentials=credentials)
        self._media_downloader = MediaIoBaseDownload
        self._include_shared_drives = include_shared_drives

    def list_files(
        self,
        folder_id: str,
        mime_types: list[str],
        extensions: list[str],
        excluded_folder_name_contains: list[str],
        excluded_folder_names: list[str],
        recursive: bool,
        max_files: int | None = None,
        progress: ProgressReporter | None = None,
    ) -> list[DriveFileInfo]:
        return self._list_folder_files(
            folder_id=folder_id,
            folder_path="",
            mime_types=mime_types,
            extensions=extensions,
            excluded_folder_name_contains=excluded_folder_name_contains,
            excluded_folder_names=excluded_folder_names,
            recursive=recursive,
            visited_folder_ids=set(),
            max_files=max_files,
            progress=progress,
        )

    def _list_folder_files(
        self,
        folder_id: str,
        folder_path: str,
        mime_types: list[str],
        extensions: list[str],
        excluded_folder_name_contains: list[str],
        excluded_folder_names: list[str],
        recursive: bool,
        visited_folder_ids: set[str],
        max_files: int | None,
        progress: ProgressReporter | None,
    ) -> list[DriveFileInfo]:
        if folder_id in visited_folder_ids:
            return []
        visited_folder_ids.add(folder_id)
        _report(progress, f"Scanning folder: {folder_path or folder_id}")

        # Drive does not provide a reliable DWG mime type in every workspace.
        # We list folders broadly, then apply extension filtering locally.
        escaped_folder_id = folder_id.replace("'", "\\'")
        folder_mime_type = "application/vnd.google-apps.folder"
        query = f"'{escaped_folder_id}' in parents and trashed = false"
        mime_query = " or ".join(f"mimeType = '{mime_type}'" for mime_type in mime_types)
        if mime_query and not extensions:
            folder_query = f"mimeType = '{folder_mime_type}'"
            query = f"{query} and ({mime_query} or {folder_query})"

        files: list[DriveFileInfo] = []
        page_token: str | None = None

        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    fields=(
                        "nextPageToken, files(id, name, mimeType, modifiedTime, "
                        "md5Checksum, size, parents)"
                    ),
                    pageToken=page_token,
                    pageSize=1000,
                    supportsAllDrives=self._include_shared_drives,
                    includeItemsFromAllDrives=self._include_shared_drives,
                )
                .execute()
            )
            for file in response.get("files", []):
                if max_files is not None and len(files) >= max_files:
                    return files
                drive_file = _drive_file_from_api(file)
                if drive_file.mime_type == folder_mime_type:
                    # Archive/OLD folders are skipped before recursion so their children
                    # are never listed or downloaded.
                    if _is_excluded_folder(
                        drive_file.name,
                        excluded_folder_name_contains,
                        excluded_folder_names,
                    ):
                        _report(progress, f"Skipping excluded folder: {_join_drive_path(folder_path, drive_file.name)}")
                    elif recursive:
                        child_path = _join_drive_path(folder_path, drive_file.name)
                        files.extend(
                            self._list_folder_files(
                                folder_id=drive_file.id,
                                folder_path=child_path,
                                mime_types=mime_types,
                                extensions=extensions,
                                excluded_folder_name_contains=excluded_folder_name_contains,
                                excluded_folder_names=excluded_folder_names,
                                recursive=recursive,
                                visited_folder_ids=visited_folder_ids,
                                max_files=None if max_files is None else max_files - len(files),
                                progress=progress,
                            )
                        )
                elif _is_allowed_file(drive_file, mime_types, extensions):
                    drive_file = DriveFileInfo(
                        id=drive_file.id,
                        name=drive_file.name,
                        mime_type=drive_file.mime_type,
                        modified_time=drive_file.modified_time,
                        checksum=drive_file.checksum,
                        parent_id=drive_file.parent_id,
                        drive_path=_join_drive_path(folder_path, drive_file.name),
                    )
                    files.append(drive_file)
                    _report(progress, f"Found drawing: {drive_file.drive_path or drive_file.name}")
                    if max_files is not None and len(files) >= max_files:
                        return files

            page_token = response.get("nextPageToken")
            if not page_token:
                return files

    def download_file(self, file_id: str, destination: Path) -> Path:
        request = self._service.files().get_media(
            fileId=file_id,
            supportsAllDrives=self._include_shared_drives,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)

        buffer = io.BytesIO()
        downloader = self._media_downloader(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        destination.write_bytes(buffer.getvalue())
        return destination


class LocalFixtureDriveClient(DriveClient):
    """Development client that treats a local folder as the Drive source."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_files(
        self,
        folder_id: str,
        mime_types: list[str],
        extensions: list[str],
        excluded_folder_name_contains: list[str],
        excluded_folder_names: list[str],
        recursive: bool,
        max_files: int | None = None,
        progress: ProgressReporter | None = None,
    ) -> list[DriveFileInfo]:
        del folder_id
        suffix_to_mime = {
            ".pdf": "application/pdf",
            ".svg": "image/svg+xml",
            ".dxf": "application/dxf",
            ".dwg": "application/octet-stream",
        }
        files: list[DriveFileInfo] = []
        source_paths = self.root.rglob("*") if recursive else self.root.iterdir()
        for path in source_paths:
            if not path.is_file():
                continue
            if _has_excluded_folder(
                path.relative_to(self.root),
                excluded_folder_name_contains,
                excluded_folder_names,
            ):
                _report(progress, f"Skipping excluded local path: {path.relative_to(self.root)}")
                continue
            mime_type = suffix_to_mime.get(path.suffix.lower())
            if not mime_type:
                continue
            drive_path = path.relative_to(self.root).as_posix()
            drive_file = DriveFileInfo(
                id=drive_path,
                name=path.name,
                mime_type=mime_type,
                drive_path=drive_path,
            )
            if _is_allowed_file(drive_file, mime_types, extensions):
                files.append(drive_file)
                _report(progress, f"Found local drawing: {drive_file.drive_path or drive_file.name}")
                if max_files is not None and len(files) >= max_files:
                    return files
        return files

    def download_file(self, file_id: str, destination: Path) -> Path:
        source = self.root / file_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination


def sync_drive_folder(
    client: DriveClient,
    folder_id: str,
    allowed_mime_types: list[str],
    allowed_extensions: list[str],
    excluded_folder_name_contains: list[str],
    excluded_folder_names: list[str],
    recursive: bool,
    preserve_drive_paths: bool,
    raw_dir: Path,
    metadata_dir: Path,
    max_files: int | None = None,
    list_only: bool = False,
    progress: ProgressReporter | None = None,
) -> list[DriveFileInfo]:
    _report(progress, "Listing Drive files...")
    files = client.list_files(
        folder_id=folder_id,
        mime_types=allowed_mime_types,
        extensions=allowed_extensions,
        excluded_folder_name_contains=excluded_folder_name_contains,
        excluded_folder_names=excluded_folder_names,
        recursive=recursive,
        max_files=max_files,
        progress=progress,
    )
    _report(progress, f"Matched {len(files)} drawing file(s).")
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    for index, file in enumerate(files, start=1):
        if list_only:
            continue
        destination = _download_path(raw_dir, file, preserve_drive_paths)
        _report(progress, f"Downloading {index}/{len(files)}: {file.drive_path or file.name}")
        client.download_file(file.id, destination)

    manifest_path = metadata_dir / "drive-files.json"
    manifest_path.write_text(
        json.dumps([_drive_file_to_json(file) for file in files], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return files


def _drive_file_from_api(file: dict[str, Any]) -> DriveFileInfo:
    parents = file.get("parents") or []
    return DriveFileInfo(
        id=file["id"],
        name=file["name"],
        mime_type=file["mimeType"],
        modified_time=file.get("modifiedTime"),
        checksum=file.get("md5Checksum"),
        parent_id=parents[0] if parents else None,
    )


def _drive_file_to_json(file: DriveFileInfo) -> dict[str, str | None]:
    return {
        "id": file.id,
        "name": file.name,
        "mime_type": file.mime_type,
        "modified_time": file.modified_time,
        "checksum": file.checksum,
        "parent_id": file.parent_id,
        "drive_path": file.drive_path,
    }


def _safe_filename(name: str) -> str:
    blocked = '<>:"/\\|?*'
    safe = "".join("_" if char in blocked else char for char in name).strip()
    return safe or "unnamed-drawing"


def _download_filename(file: DriveFileInfo) -> str:
    # Keep the original drawing filename. CAD XREF references often depend on
    # exact sibling filenames, so adding Drive ids can break referenced drawings.
    return _safe_filename(file.name)


def _download_path(raw_dir: Path, file: DriveFileInfo, preserve_drive_paths: bool) -> Path:
    if not preserve_drive_paths or not file.drive_path:
        return raw_dir / _download_filename(file)

    # Keep Drive folder context because it is useful later for discipline/floor hints.
    path_parts = Path(file.drive_path).parts
    if len(path_parts) == 1:
        return raw_dir / _download_filename(file)

    folder_parts = [_safe_filename(part) for part in path_parts[:-1]]
    return raw_dir.joinpath(*folder_parts) / _download_filename(file)


def _join_drive_path(folder_path: str, name: str) -> str:
    return f"{folder_path}/{name}" if folder_path else name


def _is_allowed_file(
    file: DriveFileInfo,
    allowed_mime_types: list[str],
    allowed_extensions: list[str],
) -> bool:
    normalized_extensions = {
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in allowed_extensions
    }
    suffix = Path(file.name).suffix.lower()

    return file.mime_type in allowed_mime_types or suffix in normalized_extensions


def _is_excluded_folder(
    folder_name: str,
    excluded_name_contains: list[str],
    excluded_names: list[str],
) -> bool:
    normalized_folder_name = folder_name.casefold()
    contains_terms = [term.casefold() for term in excluded_name_contains]
    exact_names = {name.casefold() for name in excluded_names}

    return (
        any(term in normalized_folder_name for term in contains_terms)
        or normalized_folder_name in exact_names
    )


def _has_excluded_folder(
    relative_path: Path,
    excluded_name_contains: list[str],
    excluded_names: list[str],
) -> bool:
    return any(
        _is_excluded_folder(part, excluded_name_contains, excluded_names)
        for part in relative_path.parts[:-1]
    )


def _report(progress: ProgressReporter | None, message: str) -> None:
    if progress:
        progress(message)
