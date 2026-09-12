"""WebChat upload limits; not a policy for any other channel."""


DEFAULT_MEDIA_TYPES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm", "audio/mp4",
})


def validate_webchat_attachments(channel, files):
    if channel.platform != "WebChat":
        raise ValueError("WebChat attachment policy cannot be used for another channel")
    policy = (channel.config or {}).get("webchat_uploads", {})
    maximum = int(policy.get("max_files", 5))
    max_bytes = int(policy.get("max_file_bytes", 10 * 1024 * 1024))
    max_total = int(policy.get("max_total_bytes", maximum * max_bytes))
    allowed = policy.get("content_types", DEFAULT_MEDIA_TYPES)
    if len(files) > maximum:
        raise ValueError(f"A message can contain at most {maximum} attachments")
    if sum(upload.size for upload in files) > max_total:
        raise ValueError("The combined attachments exceed the upload limit")
    for upload in files:
        if upload.size > max_bytes or upload.content_type not in allowed:
            raise ValueError("An attachment exceeds the size limit or has an unsupported content type")
