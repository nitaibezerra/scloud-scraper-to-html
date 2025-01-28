import os
import re
import subprocess
import logging
import requests

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
    (using `scdl`), and generate an HTML page listing the downloaded tracks.
    """

    def __init__(self, base_dir="html", sub_dir_name="soundcloud_downloads"):
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

        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        logging.debug(
            f"Initialized SoundCloudDownloader with output directory: {self.output_dir}"
        )

    def process_strings(self, strings):
        """
        Public method to process a list of strings. It extracts SoundCloud links,
        resolves short URLs, downloads the tracks, and generates the HTML listing.

        :param strings: List of strings that may contain SoundCloud links
        """
        logging.info("Starting to process strings.")
        self._extract_soundcloud_links(strings)
        logging.info(
            f"Extracted {len(self._soundcloud_links)} SoundCloud links: {self._soundcloud_links}"
        )

        self._resolve_short_links()
        logging.info("Resolved short links to full URLs.")

        self._download_tracks()
        logging.info("Completed downloading tracks.")

        self._generate_html_page()
        logging.info("Generated HTML page.")

    def _extract_soundcloud_links(self, strings):
        """
        Private method to extract SoundCloud links from the list of strings.
        Matches both short links (on.soundcloud.com) and full links (soundcloud.com).
        Duplicates are removed and stored in self._soundcloud_links.

        :param strings: List of strings that may contain SoundCloud links
        """
        logging.debug("Extracting SoundCloud links from input strings.")
        pattern = r"(https?://(?:on\.soundcloud\.com|soundcloud\.com)/[^\s]+)"
        found_links = []

        for text in strings:
            matches = re.findall(pattern, text)
            found_links.extend(matches)

        # Remove duplicates
        self._soundcloud_links = list(set(found_links))
        logging.debug(f"Found links: {self._soundcloud_links}")

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
            else:
                resolved_links.append(link)

        self._soundcloud_links = resolved_links

    def _download_tracks(self):
        """
        Private method that iterates over the stored SoundCloud links and
        downloads the tracks in MP3 format using the `scdl` utility.
        The result of each download (link + names of MP3 files) is stored
        in self._download_results.
        """
        logging.debug("Starting to download tracks.")
        for link in self._soundcloud_links:
            logging.info(f"Downloading from link: {link}")
            files_before = set(os.listdir(self.output_dir))
            self._run_scdl_command(link)
            files_after = set(os.listdir(self.output_dir))

            # Identify only the newly downloaded MP3 files
            new_files = files_after - files_before
            mp3_files = [f for f in new_files if f.lower().endswith(".mp3")]

            if mp3_files:
                logging.info(f"Downloaded files: {mp3_files}")
                self._download_results.append((link, mp3_files))
            else:
                logging.warning(f"No files downloaded for link: {link}")

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

    def _generate_html_page(self):
        """
        Private method to generate an HTML page (index.html) listing the
        downloaded tracks in the directory self.output_dir. Each track includes
        its title, an audio player, and a link to the original SoundCloud page.
        """
        logging.debug("Generating HTML page.")
        html_path = os.path.join(self.output_dir, "index.html")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html lang='en'>\n")
            f.write("<head>\n")
            f.write("  <meta charset='utf-8'/>\n")
            f.write("  <title>Downloaded Tracks</title>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("  <h1>Downloaded Tracks from SoundCloud</h1>\n")

            for link, mp3_files in self._download_results:
                for mp3_file in mp3_files:
                    title = os.path.splitext(mp3_file)[0]
                    mp3_path = (
                        mp3_file  # Adjust if using a different directory structure
                    )

                    f.write("  <div>\n")
                    f.write(f"    <h2>{title}</h2>\n")
                    f.write("    <audio controls>\n")
                    f.write(f"      <source src='{mp3_path}' type='audio/mpeg'>\n")
                    f.write("    </audio>\n")
                    f.write(
                        f"    <p><a href='{link}' target='_blank'>Original SoundCloud Link</a></p>\n"
                    )
                    f.write("  </div>\n")
                    f.write("  <hr/>\n")

            f.write("</body>\n")
            f.write("</html>\n")

        logging.info(f"HTML page generated at: {html_path}")


def main():
    """
    Main function to run the script directly. It processes a predefined
    list of SoundCloud links, downloads the tracks, and generates an HTML page.
    """
    strings = [
        "A2 - https://on.soundcloud.com/axJaEesGeWmSFbSP9",
        "B1 https://on.soundcloud.com/KG2gZ6KqNwbZrM4q9",
        "https://on.soundcloud.com/4ht4PfBFpsLjFSnx9",
        "https://on.soundcloud.com/oWAvTRXLWSN9BXLV8",
        "B4 https://on.soundcloud.com/41vQDeBNFVnh4PAB8",
        "B5 https://on.soundcloud.com/w4o34Yk8hDy8iJTj6",
        "B6 https://on.soundcloud.com/XXMCejYF6ySkJ6Nm9",
        "B7 https://on.soundcloud.com/sCgPPArMLFxd4bsK8",
        "B8 https://on.soundcloud.com/55N3TqKMVwPUMuYY7",
        "B9 https://on.soundcloud.com/G9dKEZVpCgGPZATo9",
        "B10 https://on.soundcloud.com/VkWWKFPKKmX3Rznn6",
        "B11 https://on.soundcloud.com/9bQvbKfx8qH96GcW6",
        "B12 https://on.soundcloud.com/1q4jQM4EWWUTusgG7",
    ]

    logging.info("Starting SoundCloudDownloader script.")
    downloader = SoundCloudDownloader(
        base_dir="html", sub_dir_name="soundcloud_downloads"
    )
    downloader.process_strings(strings)
    logging.info("Finished processing SoundCloud links.")


if __name__ == "__main__":
    main()
