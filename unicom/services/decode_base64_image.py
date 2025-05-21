from django.conf import settings
import base64
import uuid
import os



def decode_base64_image(base64_string, output_subdir="media"):
    """
    Decodes a base64-encoded image and writes it into:
      <settings.MEDIA_ROOT>/<output_subdir>/<uuid>.jpg
    Returns the *relative* path "media/<uuid>.jpg" (i.e. no leading slash).
    
    So physically:   /my_project/media/media/<uuid>.jpg
    DB storage:      "media/<uuid>.jpg"
    Final serve URL: <MEDIA_URL>/media/<uuid>.jpg => /media/media/<uuid>.jpg
    """
    # 1) Physical directory
    physical_dir = os.path.join(settings.MEDIA_ROOT, output_subdir)
    os.makedirs(physical_dir, exist_ok=True)

    # 2) Generate filename
    filename = f"{uuid.uuid4()}.jpg"
    full_path = os.path.join(physical_dir, filename)

    # 3) Write the file
    with open(full_path, "wb") as f:
        f.write(base64.b64decode(base64_string))

    # 4) Return the relative DB path: "media/<uuid>.jpg"
    return os.path.join(output_subdir, filename)