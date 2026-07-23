import unittest
from unittest.mock import Mock, patch

from instagram_publisher import (
    InstagramPublishError,
    crear_contenedor_story,
    esperar_contenedor_listo,
    publicar_story,
)


def mock_response(ok: bool, json_data: dict, text: str = "") -> Mock:
    response = Mock()
    response.ok = ok
    response.json.return_value = json_data
    response.text = text
    return response


class CrearContenedorStoryTests(unittest.TestCase):
    @patch("instagram_publisher.requests.post")
    def test_returns_container_id(self, mock_post):
        mock_post.return_value = mock_response(True, {"id": "container-123"})
        container_id = crear_contenedor_story("https://example.com/x.png", "ig-user", "token")
        self.assertEqual(container_id, "container-123")

    @patch("instagram_publisher.requests.post")
    def test_raises_on_error_response(self, mock_post):
        mock_post.return_value = mock_response(False, {}, text="bad request")
        with self.assertRaises(InstagramPublishError):
            crear_contenedor_story("https://example.com/x.png", "ig-user", "token")


class EsperarContenedorListoTests(unittest.TestCase):
    @patch("instagram_publisher.time.sleep", return_value=None)
    @patch("instagram_publisher.requests.get")
    def test_returns_when_finished(self, mock_get, _mock_sleep):
        mock_get.return_value = mock_response(True, {"status_code": "FINISHED"})
        esperar_contenedor_listo("container-123", "token")

    @patch("instagram_publisher.time.sleep", return_value=None)
    @patch("instagram_publisher.requests.get")
    def test_raises_on_error_status(self, mock_get, _mock_sleep):
        mock_get.return_value = mock_response(True, {"status_code": "ERROR"})
        with self.assertRaises(InstagramPublishError):
            esperar_contenedor_listo("container-123", "token")

    @patch("instagram_publisher.time.sleep", return_value=None)
    @patch("instagram_publisher.requests.get")
    def test_raises_timeout_when_never_finished(self, mock_get, _mock_sleep):
        mock_get.return_value = mock_response(True, {"status_code": "IN_PROGRESS"})
        with self.assertRaises(TimeoutError):
            esperar_contenedor_listo("container-123", "token", timeout_s=0)


class PublicarStoryTests(unittest.TestCase):
    @patch("instagram_publisher.requests.post")
    def test_returns_media_id(self, mock_post):
        mock_post.return_value = mock_response(True, {"id": "media-456"})
        media_id = publicar_story("container-123", "ig-user", "token")
        self.assertEqual(media_id, "media-456")

    @patch("instagram_publisher.requests.post")
    def test_raises_on_error_response(self, mock_post):
        mock_post.return_value = mock_response(False, {}, text="bad request")
        with self.assertRaises(InstagramPublishError):
            publicar_story("container-123", "ig-user", "token")


if __name__ == "__main__":
    unittest.main()
