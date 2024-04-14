import time
import uuid
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import jwt
import requests
from pydantic import BaseModel


class Permission(BaseModel):
    path: str
    methods: List[str]
    query: Dict[str, Any]


class Goflet:
    base_url: str
    jwt_algorithm: str
    jwt_secret: Optional[str]
    jwt_private_key: Optional[str]
    jwt_issuer: str
    jwt_expiration: int

    def __init__(
        self,
        base_url: str,
        jwt_algorithm: str,
        jwt_secret: Optional[str],
        jwt_private_key: Optional[str],
        jwt_issuer: str,
        jwt_expiration: int,
    ):
        self.base_url = base_url
        self.jwt_algorithm = jwt_algorithm
        self.jwt_secret = jwt_secret
        self.jwt_private_key = jwt_private_key
        self.jwt_issuer = jwt_issuer
        self.jwt_expiration = jwt_expiration

    @staticmethod
    def _generate_uuid() -> str:
        return str(uuid.uuid4())

    def _generate_header(self) -> dict:
        return {
            "alg": self.jwt_algorithm,
            "typ": "JWT",
        }

    def _generate_jwt(self, payload: dict) -> str:
        payload["iss"] = self.jwt_issuer
        payload["iat"] = payload.get("iat", int(time.time()))
        payload["nbf"] = payload.get("nbf", int(time.time()) - 1)
        payload["exp"] = payload.get("exp", self.jwt_expiration + int(time.time()))
        payload["kid"] = f"{int(time.time())}-{self._generate_uuid()}"
        header = self._generate_header()

        if self.jwt_algorithm.startswith("HS"):
            secret = self.jwt_secret
        else:
            secret = self.jwt_private_key

        return jwt.encode(payload, secret, algorithm=self.jwt_algorithm, headers=header)

    def generate_jwt(self, permissions: List[Permission]) -> str:
        """
        Generate JWT token with permissions.
        :param permissions: Permissions
        :param user_id: User ID
        :return: JWT token
        """
        payload = {
            "permissions": [
                {
                    "path": permission.path,
                    "methods": permission.methods,
                    "query": permission.query,
                }
                for permission in permissions
            ],
        }
        return self._generate_jwt(payload)

    def generate_url(self, path: str, method: str, query: Dict[str, Any]) -> str:
        """
        Generate URL with query parameters.
        :param path: URL path
        :param method: HTTP method
        :param query: Query parameters
        :return: URL with query parameters
        """
        url = f"{self.base_url}{path}"
        jwt_token = self.generate_jwt(
            permissions=[Permission(path=path, methods=[method], query=query)]
        )
        query["token"] = jwt_token
        quoted_query = "&".join(f"{k}={quote(str(v))}" for k, v in query.items())
        return f"{url}?{quoted_query}"

    def create_upload_session(self, file_path: str) -> str:
        """
        Start upload session
        :param file_path: File path
        :return: URL with query parameters
        """
        return self.generate_url(f"/upload/{file_path}", "PUT", {})

    def cancel_upload_session(self, file_path: str):
        """
        Cancel upload session
        :param file_path: File path
        """
        url = self.generate_url(f"/upload/{file_path}", "DELETE", {})
        result = requests.delete(url)
        if result.status_code >= 400:
            raise RuntimeError(result.json())

    def complete_upload_session(self, file_path: str):
        """
        Complete upload session
        :param file_path: File path
        """
        url = self.generate_url(f"/upload/{file_path}", "POST", {})
        result = requests.post(url)
        if result.status_code >= 400:
            raise RuntimeError(result.json())

    def create_download_url(self, file_path: str) -> str:
        """
        Complete upload session
        :param file_path: File path
        :return: URL with query parameters
        """
        return self.generate_url(f"/file/{file_path}", "GET", {})

    def get_file_meta(self, file_path: str) -> Dict[str, Any]:
        """
        Get file metadata
        :param file_path: File path
        :return: File metadata
        """
        meta_url = self.generate_url(f"/api/meta/{file_path}", "GET", {})
        result = requests.get(meta_url)
        if result.status_code >= 400:
            raise RuntimeError(result.json())
        return result.json()

    def delete_file(self, file_path: str):
        """
        Delete file
        :param file_path: File path
        :return: File metadata
        """
        meta_url = self.generate_url(f"/file/{file_path}", "DELETE", {})
        result = requests.delete(meta_url)
        if result.status_code >= 400:
            raise RuntimeError(result.json())

    def create_empty_file(self, file_path: str) -> str:
        """
        Create empty file
        :param file_path: File path
        :return: File metadata
        """
        meta_url = self.generate_url(f"/api/action/create", "POST", {})
        payload = {
            "path": file_path,
        }
        result = requests.post(meta_url, json=payload)
        if result.status_code >= 400:
            raise RuntimeError(result.json())
        return self.create_download_url(file_path)

    def copy_file(
        self, file_path: str, new_file_path: str, on_conflict="overwrite"
    ) -> str:
        """
        Copy file
        :param file_path: File path
        :param new_file_path: New file path
        :param on_conflict: On conflict strategy
        :return: File metadata
        """
        meta_url = self.generate_url(f"/api/action/copy", "POST", {})
        payload = {
            "sourcePath": file_path,
            "targetPath": new_file_path,
            "onConflict": on_conflict,
        }
        result = requests.post(meta_url, json=payload)
        if result.status_code >= 400:
            raise RuntimeError(result.json())
        return self.create_download_url(new_file_path)

    def move_file(
        self, file_path: str, new_file_path: str, on_conflict="overwrite"
    ) -> str:
        """
        Move file
        :param file_path: File path
        :param new_file_path: New file path
        :param on_conflict: On conflict strategy
        :return: File metadata
        """
        meta_url = self.generate_url(f"/api/action/move", "POST", {})
        payload = {
            "sourcePath": file_path,
            "targetPath": new_file_path,
            "onConflict": on_conflict,
        }
        result = requests.post(meta_url, json=payload)
        if result.status_code >= 400:
            raise RuntimeError(result.json())
        return self.create_download_url(new_file_path)

    def onlyoffice_callback(self, data: Dict[str, Any], file_path: str):
        """
        OnlyOffice callback
        :param data: Callback data
        :param file_path: File path
        :return: None
        """
        meta_url = self.generate_url(f"/api/onlyoffice/{file_path}", "POST", {})
        result = requests.post(meta_url, json=data)
        if result.status_code >= 400:
            raise RuntimeError(result.json())