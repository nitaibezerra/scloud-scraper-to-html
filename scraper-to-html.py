import argparse
import logging
import os
import re
import shutil
import subprocess
import unicodedata
import zipfile

import requests
import yaml  # Biblioteca para carregar arquivos YAML
from mutagen.id3 import APIC, ID3

# For extracting album art
from HTML_page_generator import SoundCloudHTMLPageGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class SoundCloudDownloader:
    """
    A class to extract SoundCloud links from a list of strings,
    resolve short links if necessary, download the associated MP3 files
    (using `scdl`), extract embedded images, and generate an HTML page
    listing the downloaded tracks (with an option to download all as a ZIP).
    """

    def __init__(self, base_dir, sub_dir_name="soundcloud_downloads"):
        """
        Initializes the downloader with a base directory and a subdirectory
        to store downloads and the HTML page.

        :param base_dir: Base directory where the HTML folder will be created (default: "html")
        :param sub_dir_name: Subdirectory name where MP3 files and the HTML file will be saved
        """
        self.base_dir = base_dir
        self.sub_dir_name = sub_dir_name
        self.output_dir = os.path.join(self.base_dir, self.sub_dir_name)

        self._soundcloud_links = []
        self._download_results = []
        self._unique_tracks = (
            set()
        )  # Set to keep track of unique normalized MP3 filenames

        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        # Also create an img/ subdirectory for cover art
        self.img_dir = os.path.join(self.output_dir, "img")
        os.makedirs(self.img_dir, exist_ok=True)

        logging.debug(
            f"Initialized SoundCloudDownloader with output directory: {self.output_dir}"
        )

    def process_strings(self, strings):
        """
        Public method to process a list of strings. It extracts SoundCloud links,
        resolves short URLs, downloads the tracks, extracts images, and
        generates the HTML listing (with a ZIP download link).
        Finally, it copies the playAll.js script to the output directory.
        """
        logging.info("Starting to process strings.")
        self._extract_soundcloud_links(strings)
        logging.info(
            f"Extracted {len(self._soundcloud_links)} SoundCloud links: {self._soundcloud_links}"
        )

        self._resolve_short_links()
        logging.info("Resolved short links to full URLs.")

        self._download_tracks()
        logging.info("Completed downloading tracks (and extracted images).")

        # Generate ZIP before creating HTML, so the HTML can link to it
        self._create_zip()
        logging.info("Created ZIP file with all tracks.")

        self._generate_html_page()
        logging.info("Generated HTML page.")

        # Copy playAll.js to the output directory
        self._copy_static_files_to_output_dir()

    def _extract_soundcloud_links(self, strings):
        """
        Private method to extract SoundCloud links from the list of strings in the order
        they appear (avoiding duplicates). Matches both short links (on.soundcloud.com)
        and full links (soundcloud.com). This preserves the original order from the input.

        :param strings: List of strings that may contain SoundCloud links
        """
        logging.debug("Extracting SoundCloud links from input strings.")
        pattern = r"(https?://(?:on\.soundcloud\.com|soundcloud\.com)/[^\s]+)"
        found_links = []

        for text in strings:
            matches = re.findall(pattern, text)
            for link in matches:
                if link not in found_links:
                    found_links.append(link)

        self._soundcloud_links = found_links
        logging.debug(f"Found links (in order): {self._soundcloud_links}")

    def _resolve_short_links(self):
        """
        Private method to resolve short SoundCloud links (on.soundcloud.com)
        to their full URLs using HTTP requests. Updates the links in place.
        """
        logging.debug("Resolving short SoundCloud links to full URLs.")
        resolved_links = []
        for link in self._soundcloud_links:
            if "on.soundcloud.com" in link:
                try:
                    logging.debug(f"Resolving short link: {link}")
                    response = requests.head(link, allow_redirects=True)
                    full_url = response.url
                    logging.debug(f"Resolved {link} to {full_url}")
                    resolved_links.append(full_url)
                except requests.RequestException as e:
                    logging.error(f"Failed to resolve short link {link}: {e}")
                    # Keep the original link if resolution fails
                    resolved_links.append(link)
            else:
                resolved_links.append(link)

        self._soundcloud_links = resolved_links

    def _download_tracks(self):
        """
        Private method that iterates over the stored SoundCloud links and
        downloads the tracks in MP3 format using the `scdl` utility.
        For each MP3 downloaded, we also attempt to extract the image.
        The result (mp3 file + image file) is stored in self._download_results,
        with a global set (self._unique_tracks) preventing duplicates.
        """
        logging.debug("Starting to download tracks.")
        for link in self._soundcloud_links:
            logging.info(f"Downloading from link: {link}")

            files_before = set(os.listdir(self.output_dir))
            self._run_scdl_command(link)
            files_after = set(os.listdir(self.output_dir))

            # Identify only the newly downloaded MP3 files
            new_files = files_after - files_before
            raw_mp3_files = [f for f in new_files if f.lower().endswith(".mp3")]

            track_data_for_this_link = []

            for raw_name in raw_mp3_files:
                norm_name = _normalize_filename(raw_name)

                # Skip if we've already processed this track
                if norm_name in self._unique_tracks:
                    logging.warning(f"Skipping duplicate track: {norm_name}")
                    continue

                # Mark this as new
                self._unique_tracks.add(norm_name)

                # OPTIONAL: Normalize filename on disk
                if raw_name != norm_name:
                    old_path = os.path.join(self.output_dir, raw_name)
                    new_path = os.path.join(self.output_dir, norm_name)
                    try:
                        os.rename(old_path, new_path)
                        logging.info(
                            f"Renamed '{raw_name}' -> '{norm_name}' for normalization."
                        )
                    except Exception as e:
                        logging.error(f"Failed to rename file '{raw_name}': {e}")
                        norm_name = raw_name

                # Extract cover image for this track
                cover_img = self._extract_image(norm_name)
                track_data_for_this_link.append((norm_name, cover_img))
                logging.info(f"Downloaded file: {norm_name}, cover: {cover_img}")

            # Append results only if new MP3 files were found
            if track_data_for_this_link:
                self._download_results.append((link, track_data_for_this_link))
            else:
                logging.warning(f"No new MP3 files for link: {link}")

    def _run_scdl_command(self, link):
        """
        Private method to execute the `scdl` command for downloading a specific link.
        Prints an error message to the console if the command fails.

        :param link: SoundCloud URL to download
        """
        cmd = ["scdl", "-l", link, "--path", self.output_dir]
        try:
            logging.debug(f"Executing command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error downloading {link}: {e}")

    def _extract_image(self, mp3_file):
        """
        Private method to extract an embedded image (cover art) from a downloaded MP3.
        If found, saves it into self.img_dir using the same base name as mp3_file.
        Returns the filename of the image (or None if not found).
        """
        mp3_path = os.path.join(self.output_dir, mp3_file)
        try:
            audio = ID3(mp3_path)
            apic_tags = audio.getall("APIC")
            if not apic_tags:
                logging.warning(f"No embedded image found in {mp3_file}.")
                return None

            # Take the first image if multiple
            cover_tag = apic_tags[0]
            mime_type = cover_tag.mime
            if mime_type == "image/jpeg":
                extension = ".jpg"
            elif mime_type == "image/png":
                extension = ".png"
            else:
                extension = ".jpg"

            image_filename = os.path.splitext(mp3_file)[0] + extension
            image_path = os.path.join(self.img_dir, image_filename)

            with open(image_path, "wb") as img:
                img.write(cover_tag.data)

            return image_filename
        except Exception as e:
            logging.warning(f"Error extracting image from {mp3_file}: {e}")
            return None

    def _create_zip(self):
        """
        Private method to create a ZIP file containing all downloaded MP3s.
        The ZIP file is placed in self.output_dir as 'all_tracks.zip'.
        """
        zip_path = os.path.join(self.output_dir, "all_tracks.zip")
        logging.debug(f"Creating ZIP file at {zip_path}.")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Iterate over all downloaded results
            for link, track_data in self._download_results:
                for mp3_file, cover_img in track_data:
                    mp3_fullpath = os.path.join(self.output_dir, mp3_file)
                    zipf.write(mp3_fullpath, arcname=mp3_file)

        logging.info(f"ZIP file created: {zip_path}")

    def _generate_html_page(self):
        """
        Private method to delegate HTML generation to the SoundCloudHTMLPageGenerator.
        """
        generator = SoundCloudHTMLPageGenerator(
            download_results=self._download_results, output_dir=self.output_dir
        )
        generator.generate_html_page()

    def _copy_static_files_to_output_dir(self):
        """
        Private method to copy static files ('playAll.js' and 'style.css')
        from the script directory to the destination directory (self.output_dir).
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        files_to_copy = ["playAll.js", "style.css"]

        for filename in files_to_copy:
            source_path = os.path.join(script_dir, filename)
            destination_path = os.path.join(self.output_dir, filename)

            try:
                shutil.copy(source_path, destination_path)
                logging.info(f"Copied '{filename}' to {destination_path}")
            except FileNotFoundError:
                logging.error(
                    f"'{filename}' not found in the script directory: {source_path}"
                )
            except Exception as e:
                logging.error(f"Error copying '{filename}': {e}")


def _normalize_filename(filename):
    """
    Normalizes a filename to NFC form to avoid duplication due to different
    Unicode normalizations (particularly on macOS).
    """
    return unicodedata.normalize("NFC", filename)


def load_links_from_yaml(file_path):
    """
    Carrega a lista de links do SoundCloud a partir de um arquivo YAML.
    Se o arquivo não existir ou estiver mal formatado, exibe um erro e retorna uma lista vazia.
    """
    if not os.path.exists(file_path):
        logging.error(
            f"Arquivo {file_path} não encontrado. Nenhum link será processado."
        )
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
            return data.get(
                "soundcloud_links", []
            )  # Retorna a lista ou uma lista vazia se não existir
    except yaml.YAMLError as e:
        logging.error(f"Erro ao carregar {file_path}: {e}")
        return []


def main():
    """
    Função principal para carregar links do arquivo YAML e iniciar o processo de download.
    Agora aceita um argumento de linha de comando para especificar o caminho do arquivo YAML.
    """
    parser = argparse.ArgumentParser(
        description="Processa links do SoundCloud a partir de um arquivo YAML."
    )
    parser.add_argument(
        "--yaml",
        type=str,
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "links_list.yaml"
        ),
        help="Caminho para o arquivo YAML contendo os links do SoundCloud (padrão: links_list.yaml no diretório do script).",
    )

    args = parser.parse_args()
    yaml_file = args.yaml

    # Deriva o nome-base do diretório a partir do nome do arquivo YAML
    base_name = os.path.splitext(os.path.basename(yaml_file))[0]

    logging.info(f"Carregando links do arquivo: {yaml_file}")
    strings = load_links_from_yaml(yaml_file)

    if not strings:
        logging.warning("Nenhum link carregado. Verifique o arquivo YAML.")
        return

    logging.info(f"{len(strings)} links carregados do YAML.")

    downloader = SoundCloudDownloader(
        base_dir=base_name, sub_dir_name="soundcloud_downloads"
    )
    downloader.process_strings(strings)
    logging.info("Finalizado o processamento dos links do SoundCloud.")


if __name__ == "__main__":
    main()
