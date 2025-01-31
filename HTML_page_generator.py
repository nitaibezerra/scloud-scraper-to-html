import logging
import os

from jinja2 import Template

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class SoundCloudHTMLPageGenerator:
    """
    A helper class to build the final HTML page for SoundCloud tracks,
    including a summary of all tracks, anchor links, a 'Play All' feature,
    and direct download links.
    """

    def __init__(self, download_results, output_dir):
        """
        :param download_results: The list of (soundcloud_link, [(mp3_file, cover_image), ...])
                                 preserving the original order.
        :param output_dir: The directory where MP3 files, images, and other resources are stored.
        """
        self.download_results = download_results
        self.output_dir = output_dir
        self.html_path = os.path.join(
            self.output_dir, "../index.html"
        )  # Root directory
        self.zip_name = "all_tracks.zip"
        self.zip_path = os.path.join(self.output_dir, self.zip_name)

        # Will build two lists to keep track of order:
        # 1) a sequential list of ALL mp3 filenames for the "Play All" feature
        # 2) a list of (anchor_id, mp3_file, image_file, title, link) for each track
        self.all_mp3_files = []
        self.ordered_tracks = []

    def generate_html_page(self):
        """
        Orchestrates the creation of the index.html file:
          - Collects track info in the order they were downloaded
          - Writes the HTML with a summary/anchor links
          - Inserts a 'Play All' button & script reference
        """
        self._collect_ordered_tracks()
        self._write_html()

    def _collect_ordered_tracks(self):
        """
        Collects all track data in the order they appear in download_results.
        Each track is assigned an anchor ID for direct linking.
        """
        track_count = 1
        for link, track_data in self.download_results:
            for mp3_file, image_file in track_data:
                title = os.path.splitext(mp3_file)[0]
                anchor_id = f"track-{track_count}"
                self.all_mp3_files.append(mp3_file)
                self.ordered_tracks.append(
                    {
                        "anchor_id": anchor_id,
                        "mp3_file": f"soundcloud_downloads/{mp3_file}",  # Adjust path
                        "image_file": f"soundcloud_downloads/img/{image_file}"
                        if image_file
                        else None,  # Adjust path
                        "title": title,
                        "link": link,
                    }
                )
                track_count += 1

    def _write_html(self):
        """
        Writes the complete HTML page using Jinja2 for templating.
        The template is stored in an external file `template.html` for better maintainability.
        It includes:
        - A "Play All" button to play MP3s in sequence
        - A numbered summary with anchor links to each track
        - Individual MP3 download links
        - A ZIP download link (if present)
        - Referencing an external JavaScript file (playAll.js)
        """
        logging.debug(
            "Generating the final HTML page with summary and track details using Jinja2."
        )

        # Path to the external Jinja2 template file
        template_path = os.path.join(self.output_dir, "../../template.html")

        # Check if the template exists
        if not os.path.exists(template_path):
            logging.error(f"Template file not found at {template_path}.")
            return

        # Load the template file
        with open(template_path, "r", encoding="utf-8") as template_file:
            template_str = template_file.read()

        # Create the Jinja2 template
        template = Template(template_str)

        # Render the template, passing in the dynamic data
        rendered_html = template.render(
            zip_exists=os.path.exists(self.zip_path),
            zip_name=self.zip_name,
            ordered_tracks=self.ordered_tracks,
            all_mp3_files=self.all_mp3_files,
        )

        # Write the rendered HTML to index.html in the root folder
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        logging.info(f"HTML page generated at: {self.html_path}")
