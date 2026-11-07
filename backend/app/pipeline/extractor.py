import re


def extract_code_block(text: str) -> str:
    """
    Extracts raw code inside ```python ... ``` or generic code blocks.
    Falls back to raw stripped string if no block markers are present.
    """
    pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return text.strip()

