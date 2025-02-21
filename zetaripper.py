import html
import json
import re
from pathlib import Path
from shutil import rmtree
from urllib.parse import unquote

import img2pdf
import requests
from tqdm import trange


def get_new_session(code: str, password: str) -> tuple[requests.Session, requests.Response]:
    session = requests.Session()
    session.headers = {
        'Origin': 'https://ebooks.zetamaths.com',
        'Referer': f'https://ebooks.zetamaths.com/{code}',
    }

    response = session.get(f'https://ebooks.zetamaths.com/{code}')
    response.raise_for_status()
    inertia_version = json.loads(html.unescape(re.search('data-page="(.+?)"', response.text).group(1)))['version']
    session.headers['X-Inertia'] = 'true'
    session.headers['X-Inertia-Version'] = inertia_version

    response = session.post(
        f'https://ebooks.zetamaths.com/{code}/login',
        data={'access_code': password, 'target_page': 1},
        headers={'X-Xsrf-Token': unquote(session.cookies['XSRF-TOKEN'])},
    )
    response.raise_for_status()

    return session, response


def main() -> None:
    code = input('Bookshelf code (5-character code in URL): ').strip().lower()
    password = input('Bookshelf password: ').strip()
    session, response = get_new_session(code, password)
    books = response.json()['props']['books']

    print('\n* Bookshelf')
    print('\n'.join(f'|   {i + 1:>2}. {book["name"]}' for i, book in enumerate(books)), end='\n\n')
    book_selection = input('Enter book numbers to download, or leave blank to download all: ').strip()
    if book_selection:
        download_queue = [int(num) - 1 for num in filter(None, re.split(r',?\s*', book_selection))]
    else:
        download_queue = range(len(books))

    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    for book_num in download_queue:
        pages_path = output_dir / books[book_num]['url']
        if pages_path.is_dir():
            rmtree(pages_path)
        pages_path.mkdir()
        pages_url = f'https://ebooks.zetamaths.com/{code}/{books[book_num]["url"]}'
        book = session.get(pages_url).json()['props']['book']

        for page in trange(1, book['page_count'] + 1, desc='Downloading pages'):
            while True:
                response = session.get(f'{pages_url}/pages/{page}')
                if response.ok:
                    break
                # We're probably ratelimited, so be cheeky and start a new session
                session, _ = get_new_session(code, password)
            (pages_path / f'{page}.jpg').write_bytes(response.content)

        print('Constructing PDF file')
        output_file = output_dir / f'{book["name"]}.pdf'
        output_file.write_bytes(img2pdf.convert(sorted(pages_path.iterdir(), key=lambda file: int(file.stem))))

        print(f'Saved to {output_file.resolve()}\n')


if __name__ == '__main__':
    main()
