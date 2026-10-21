MULTIPLE_ADVISOR_TERMS = ("หลายคน", "หลายท่าน", "ทุกคน", "ทุกท่าน", "ทั้งหมด", "ทั้งคู่", "สองคน", "2 คน")
IMAGE_REQUEST_TERMS = ("รูป", "ภาพ", "photo", "picture", "image")


def select_image_urls(query_text: str, results: list[dict], selected_urls: list) -> list[str]:
    query = query_text.lower()
    if any(term in query for term in MULTIPLE_ADVISOR_TERMS):
        return []

    available = list(dict.fromkeys(
        result.get("metadata", {}).get("image_url")
        for result in results
        if result.get("metadata", {}).get("type") == "image"
        and result.get("metadata", {}).get("image_url")
    ))
    if any(term in query for term in IMAGE_REQUEST_TERMS):
        return available[:1]

    valid_urls = set(available)
    return list(dict.fromkeys(
        url for url in selected_urls if isinstance(url, str) and url in valid_urls
    ))[:1]
