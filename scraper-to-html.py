import os
import re
import subprocess

class SoundCloudDownloader:
    """
    A class to extract SoundCloud links from a list of strings,
    download the associated MP3 files (using `scdl`), and generate
    an HTML page listing the downloaded tracks.
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

    def process_strings(self, strings):
        """
        Public method to process a list of strings. It extracts SoundCloud links,
        downloads the tracks, and generates the HTML listing.

        :param strings: List of strings that may contain SoundCloud links
        """
        self._extract_soundcloud_links(strings)
        self._download_tracks()
        self._generate_html_page()

    def _extract_soundcloud_links(self, strings):
        """
        Private method to extract SoundCloud links from the list of strings.
        Duplicates are removed and stored in self._soundcloud_links.

        :param strings: List of strings that may contain SoundCloud links
        """
        pattern = r'(https?://soundcloud\.com/[^\s]+)'
        found_links = []

        for text in strings:
            matches = re.findall(pattern, text)
            found_links.extend(matches)

        # Remove duplicates
        self._soundcloud_links = list(set(found_links))

    def _download_tracks(self):
        """
        Private method that iterates over the stored SoundCloud links and
        downloads the tracks in MP3 format using the `scdl` utility.
        The result of each download (link + names of MP3 files) is stored
        in self._download_results.
        """
        for link in self._soundcloud_links:
            files_before = set(os.listdir(self.output_dir))
            self._run_scdl_command(link)
            files_after = set(os.listdir(self.output_dir))

            # Identify only the newly downloaded MP3 files
            new_files = files_after - files_before
            mp3_files = [f for f in new_files if f.lower().endswith(".mp3")]

            if mp3_files:
                self._download_results.append((link, mp3_files))

    def _run_scdl_command(self, link):
        """
        Private method to execute the `scdl` command for downloading a specific link.
        Prints an error message to the console if the command fails.

        :param link: SoundCloud URL to download
        """
        cmd = [
            "scdl",
            "--path", self.output_dir,
            "-l", link,
            "-f"
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error downloading {link}: {e}")

    def _generate_html_page(self):
        """
        Private method to generate an HTML page (index.html) listing the
        downloaded tracks in the directory self.output_dir. Each track includes
        its title, an audio player, and a link to the original SoundCloud page.
        """
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
                    mp3_path = mp3_file  # Adjust if using a different directory structure

                    f.write("  <div>\n")
                    f.write(f"    <h2>{title}</h2>\n")
                    f.write("    <audio controls>\n")
                    f.write(f"      <source src='{mp3_path}' type='audio/mpeg'>\n")
                    f.write("    </audio>\n")
                    f.write(f"    <p><a href='{link}' target='_blank'>Original SoundCloud Link</a></p>\n")
                    f.write("  </div>\n")
                    f.write("  <hr/>\n")

            f.write("</body>\n")
            f.write("</html>\n")

        print(f"HTML page generated at: {html_path}")
        print(f"MP3 files are located in: {self.output_dir}")
