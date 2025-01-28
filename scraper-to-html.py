import os
import re
import subprocess
import logging
import requests
import zipfile
import shutil

# For extracting album art
from mutagen.id3 import ID3
from mutagen.id3 import APIC

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
        # Instead of just storing (link, mp3_file_list),
        # we'll store (link, [ (mp3_file, cover_img_file), ... ]).
        self._download_results = []

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
        self._copy_js_to_output_dir()

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
                    # Keep the original link if resolution fails
                    resolved_links.append(link)
            else:
                resolved_links.append(link)

        self._soundcloud_links = resolved_links

    def _download_tracks(self):
        """
        Private method that iterates over the stored SoundCloud links and
        downloads the tracks in MP3 format using the `scdl` utility.
        For each MP3 downloaded, we also attempt to extract the embedded image.
        The result (mp3 file + image file) is stored in self._download_results.
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
                # For each MP3, try to extract the image
                track_data = []
                for mp3_file in mp3_files:
                    cover_img = self._extract_image(mp3_file)
                    track_data.append((mp3_file, cover_img))
                    logging.info(f"Downloaded file: {mp3_file}, cover: {cover_img}")

                self._download_results.append((link, track_data))
            else:
                logging.warning(f"No MP3 files downloaded for link: {link}")

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
        Private method to generate an HTML page (index.html) listing the
        downloaded tracks in the directory self.output_dir. It includes:
        - A "Play All" button to play MP3s in sequence
        - A link to download each MP3
        - A link to download the ZIP of all MP3s
        - Cover art images (if found)
        - References an external JavaScript file (playAll.js) for sequential playback
        """
        logging.debug("Generating HTML page.")
        html_path = os.path.join(self.output_dir, "index.html")
        zip_name = "all_tracks.zip"
        zip_path = os.path.join(self.output_dir, zip_name)

        # Gather all MP3s into a single list for the "Play All" functionality
        all_mp3_files = []
        for _, track_data in self._download_results:
            for mp3_file, _ in track_data:
                all_mp3_files.append(mp3_file)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html lang='en'>\n")
            f.write("<head>\n")
            f.write("  <meta charset='utf-8'/>\n")
            f.write("  <title>Downloaded Tracks</title>\n")
            f.write("</head>\n")
            f.write("<body>\n")

            f.write("  <h1>Downloaded Tracks from SoundCloud</h1>\n")

            # Button + hidden audio element for "Play All"
            f.write("  <button onclick='playAll()'>Play All</button>\n")
            f.write(
                "  <audio id='playerAll' controls style='display:block; margin-top:10px;'></audio>\n"
            )

            # Link to download the zip of all MP3s
            if os.path.exists(zip_path):
                f.write(
                    f"  <p><a href='{zip_name}' download>Download All as ZIP</a></p>\n"
                )

            # Generate track list
            for link, track_data in self._download_results:
                for mp3_file, image_file in track_data:
                    title = os.path.splitext(mp3_file)[0]

                    f.write("  <div style='margin-bottom:20px;'>\n")
                    f.write(f"    <h2>{title}</h2>\n")

                    # If there's a cover image, display it
                    if image_file:
                        f.write(
                            f"    <img src='img/{image_file}' alt='{title}' "
                            f"style='max-width:200px; display:block; margin-bottom:5px;' />\n"
                        )

                    # Audio player for this single track
                    f.write("    <audio controls>\n")
                    f.write(f"      <source src='{mp3_file}' type='audio/mpeg'>\n")
                    f.write("    </audio>\n")

                    # Direct MP3 download link
                    f.write(
                        f"    <p><a href='{mp3_file}' download>Download MP3</a></p>\n"
                    )

                    # Original SoundCloud link
                    f.write(
                        f"    <p><a href='{link}' target='_blank'>Original SoundCloud Link</a></p>\n"
                    )
                    f.write("  </div>\n")
                    f.write("  <hr/>\n")

            #
            # Place our list of MP3s into a global variable (allTracks) so the external JS can use them.
            #
            f.write("<script>\n")
            f.write("  window.allTracks = [\n")
            for mp3_file in all_mp3_files:
                f.write(f"    '{mp3_file}',\n")
            f.write("  ];\n")
            f.write("</script>\n")

            # Reference the external JavaScript file
            # Make sure playAll.js is placed in the same directory (self.output_dir) or adjust the path accordingly.
            f.write("  <script src='playAll.js'></script>\n")

            f.write("</body>\n")
            f.write("</html>\n")

        logging.info(f"HTML page generated at: {html_path}")

    def _copy_js_to_output_dir(self):
        """
        Private method to copy the 'playAll.js' file from the script directory
        to the destination directory (self.output_dir).
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        js_source_path = os.path.join(script_dir, "playAll.js")
        js_destination_path = os.path.join(self.output_dir, "playAll.js")

        try:
            shutil.copy(js_source_path, js_destination_path)
            logging.info(f"Copied 'playAll.js' to {js_destination_path}")
        except FileNotFoundError:
            logging.error(
                f"'playAll.js' not found in the script directory: {js_source_path}"
            )
        except Exception as e:
            logging.error(f"Error copying 'playAll.js': {e}")


def main():
    """
    Main function to run the script directly. It processes a predefined
    list of SoundCloud links, downloads the tracks, extracts cover art,
    creates a ZIP, and generates an HTML page.
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
