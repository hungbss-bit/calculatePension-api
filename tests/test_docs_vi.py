from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vietnamese_docs_page_is_available():
    response = client.get('/docs')
    assert response.status_code == 200
    assert 'Tài liệu API tương tác bằng tiếng Việt' in response.text
    assert "['Try it out', 'Thử nhập dữ liệu']" in response.text


def test_openapi_metadata_and_tags_are_vietnamese():
    response = client.get('/openapi.json')
    assert response.status_code == 200
    schema = response.json()
    assert schema['info']['title'] == 'API tính lương hưu BHXH'
    assert 'Tính lương hưu' in {
        tag['name'] for tag in schema.get('tags', [])
    }
    assert schema['paths']['/v1/calculatePension']['post']['summary'] == 'Dự tính mức lương hưu'
    assert 'YeuCauTinhLuongHuu' in schema['components']['schemas']
    assert 'PensionRequest' not in schema['components']['schemas']
