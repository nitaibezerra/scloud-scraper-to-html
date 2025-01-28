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
        :param output_dir: The directory where the 'index.html' and MP3 files reside.
        """
        self.download_results = download_results
        self.output_dir = output_dir
        self.html_path = os.path.join(self.output_dir, "index.html")
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
                        "mp3_file": mp3_file,
                        "image_file": image_file,
                        "title": title,
                        "link": link,
                    }
                )
                track_count += 1

    def _write_html(self):
        """
        Writes the complete HTML page using Jinja2 for templating.
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

        # Our Jinja2 template (inline). Feel free to move it into a separate file if needed.
        template_str = """<!DOCTYPE html>
    <html lang='en'>
    <head>
    <meta charset='utf-8'/>
    <title>Downloaded Tracks</title>
    </head>
    <body>
    <h1>Downloaded Tracks from SoundCloud</h1>
    <button onclick='playAll()'>Play All</button>
    <audio id='playerAll' controls style='display:block; margin-top:10px;'></audio>

    {% if zip_exists %}
    <p><a href='{{ zip_name }}' download>Download All as ZIP</a></p>
    {% endif %}

    <h2>Summary</h2>
    <ol>
    {% for track in ordered_tracks %}
        <li><a href="#{{ track.anchor_id }}">{{ track.title }}</a></li>
    {% endfor %}
    </ol>

    {% for track in ordered_tracks %}
        <div id='{{ track.anchor_id }}' style='margin-bottom:20px;'>
        <h2>{{ track.title }}</h2>
        {% if track.image_file %}
        <img src='img/{{ track.image_file }}' alt='{{ track.title }}'
            style='max-width:200px; display:block; margin-bottom:5px;' />
        {% endif %}
        <audio controls>
            <source src='{{ track.mp3_file }}' type='audio/mpeg'>
        </audio>
        <p><a href='{{ track.mp3_file }}' download>Download MP3</a></p>
        <p><a href='{{ track.link }}' target='_blank'>Original SoundCloud Link</a></p>
        </div>
        <hr/>
    {% endfor %}

    <script>
        window.allTracks = [
        {% for mp3_file in all_mp3_files %}
            "{{ mp3_file }}",
        {% endfor %}
        ];
    </script>
    <script src='playAll.js'></script>
    </body>
    </html>"""

        template = Template(template_str)

        # Render the template, passing in the dynamic data
        rendered_html = template.render(
            zip_exists=os.path.exists(self.zip_path),
            zip_name=self.zip_name,
            ordered_tracks=self.ordered_tracks,
            all_mp3_files=self.all_mp3_files,
        )

        # Write the rendered HTML to index.html
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        logging.info(f"HTML page generated at: {self.html_path}")
