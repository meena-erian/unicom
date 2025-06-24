from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import models
from django.contrib.auth.models import User
from unicom.models.constants import channels
from django.contrib.postgres.fields import ArrayField
from django.core.validators import validate_email
from fa2svg.converter import revert_to_original_fa
import uuid
import re
import os
from bs4 import BeautifulSoup
import base64
from .fields import DedupFileField, only_delete_file_if_unused
from unicom.services.get_public_origin import get_public_origin
from openai import OpenAI
from django.conf import settings
from pydub import AudioSegment
import io

if TYPE_CHECKING:
    from unicom.models import Channel

openai_client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', None))


class Message(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('html', 'HTML'),
        ('image', 'Image'),
        ('audio', 'Audio'),
    ]
    id = models.CharField(max_length=500, primary_key=True)
    channel = models.ForeignKey('unicom.Channel', on_delete=models.CASCADE)
    platform = models.CharField(max_length=100, choices=channels)
    sender = models.ForeignKey('unicom.Account', on_delete=models.RESTRICT)
    user = models.ForeignKey(User, on_delete=models.RESTRICT, null=True, blank=True)
    chat = models.ForeignKey('unicom.Chat', on_delete=models.CASCADE, related_name='messages')
    is_outgoing = models.BooleanField(null=True, default=None, help_text="True for outgoing messages, False for incoming, None for internal")
    sender_name = models.CharField(max_length=100)
    subject = models.CharField(max_length=512, blank=True, null=True, help_text="Subject of the message (only for email messages)")
    text = models.TextField()
    html = models.TextField(
        blank=True, null=True,
        help_text="Full HTML body (only for email messages)"
    )
    to  = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of To: addresses",
    )
    cc  = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of Cc: addresses",
    )
    bcc = ArrayField(
        base_field=models.EmailField(validators=[validate_email]),
        blank=True,
        default=list,
        help_text="List of Bcc: addresses",
    )
    media = models.FileField(upload_to='media/', blank=True, null=True)
    reply_to_message = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    timestamp = models.DateTimeField()
    time_sent = models.DateTimeField(null=True, blank=True)
    time_delivered = models.DateTimeField(null=True, blank=True)
    time_seen = models.DateTimeField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    seen = models.BooleanField(default=False)
    raw = models.JSONField()
    media_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='text'
    )
    # Email tracking fields
    tracking_id = models.UUIDField(default=uuid.uuid4, null=True, blank=True, help_text="Unique ID for tracking email opens and clicks")
    time_opened = models.DateTimeField(null=True, blank=True, help_text="When the email was first opened")
    opened = models.BooleanField(default=False, help_text="Whether the email has been opened")
    time_link_clicked = models.DateTimeField(null=True, blank=True, help_text="When a link in the email was first clicked")
    link_clicked = models.BooleanField(default=False, help_text="Whether any link in the email has been clicked")
    clicked_links = ArrayField(
        base_field=models.URLField(),
        blank=True,
        null=True,
        default=list,
        help_text="List of links that have been clicked"
    )
    imap_uid = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="IMAP UID for marking as seen")

    def reply_with(self, msg_dict:dict) -> Message:
        """
        Reply to this message with a dictionary containing the response.
        The dictionary can contain 'text', 'html', 'file_path', etc.
        """
        from unicom.services.crossplatform.reply_to_message import reply_to_message
        return reply_to_message(self.channel, self, msg_dict)

    @property
    def original_content_with_base64_icons(self):
        """
        Returns the HTML content with inline images as base64 and Font Awesome icons converted to base64 PNG images.
        This is the most portable format as it doesn't require any external dependencies.
        """
        from fa2svg.converter import to_inline_png_img
        html = self.html_with_base64_images if self.platform == 'Email' else self.text
        return to_inline_png_img(html) if self.platform == 'Email' else html

    @property
    def original_content_with_svg_icons(self):
        """
        Returns the HTML content with inline images as base64 and Font Awesome icons converted to inline SVG.
        This preserves vector graphics quality but may increase the HTML size.
        """
        from fa2svg.converter import revert_to_original_fa
        html = self.html_with_base64_images if self.platform == 'Email' else self.text
        return revert_to_original_fa(html) if self.platform == 'Email' else html

    @property
    def original_content_with_cdn_icons(self):
        """
        Returns the HTML content with inline images as base64 and Font Awesome icons using CDN.
        This is the lightest option but requires internet connection to load icons.
        """
        html = self.html_with_base64_images if self.platform == 'Email' else self.text
        if self.platform == 'Email' and html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Add Font Awesome CDN if not already present
            head = soup.find('head')
            if not head:
                head = soup.new_tag('head')
                soup.insert(0, head)
            if not soup.find('link', {'href': lambda x: x and 'font-awesome' in x}):
                fa_link = soup.new_tag('link', rel='stylesheet', 
                    href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css')
                head.append(fa_link)
            return str(soup)
        return html

    @property
    def html_with_base64_images(self):
        """
        Returns the HTML content with all inline image shortlinks replaced by their original base64 data, if available.
        """
        if not self.html:
            return self.html
        soup = BeautifulSoup(self.html, 'html.parser')
        # Map shortlink src to base64 for all inline images
        images = {img.get_short_id(): img for img in self.inline_images.all()}
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src', '')
            # Extract short id from src (e.g., /i/abc123 or full URL)
            m = re.search(r'/i/([A-Za-z0-9]+)', src)
            if m:
                short_id = m.group(1)
                image_obj = images.get(short_id)
                if image_obj:
                    # Read file and encode as base64
                    data = image_obj.file.read()
                    image_obj.file.seek(0)
                    mime = 'image/png'  # Default
                    if hasattr(image_obj.file, 'file') and hasattr(image_obj.file.file, 'content_type'):
                        mime = image_obj.file.file.content_type
                    elif image_obj.file.name:
                        import mimetypes
                        mime = mimetypes.guess_type(image_obj.file.name)[0] or 'image/png'
                    b64 = base64.b64encode(data).decode('ascii')
                    img_tag['src'] = f'data:{mime};base64,{b64}'
        return str(soup)

    def as_llm_chat(self, depth=10, mode="chat", system_instruction=None, multimodal=True):
        """
        Returns a list of dicts for LLM chat APIs (OpenAI, Gemini, etc), each with 'role' and 'content'.
        - depth: max number of messages to include
        - mode: 'chat' (previous N in chat) or 'thread' (follow reply_to_message chain)
        - system_instruction: if provided, prepends a system message
        - multimodal: if True, includes media (image/audio) as content or URLs
        """
        def msg_to_dict(msg):
            # Determine role
            if msg.is_outgoing is True:
                role = "assistant"
            elif msg.is_outgoing is False:
                role = "user"
            else:
                role = "system"
            # Determine content
            content = None
            if msg.media and multimodal and msg.media_type == "image":
                # Prepare data URL for image
                b64 = None
                mime = None
                try:
                    msg.media.open('rb')
                    data = msg.media.read()
                    msg.media.seek(0)
                    import mimetypes, os
                    mime = mimetypes.guess_type(msg.media.name)[0] or 'image/png'
                    b64 = base64.b64encode(data).decode('ascii')
                except Exception:
                    b64 = None
                    mime = 'image/png'
                data_url = f"data:{mime};base64,{b64}" if b64 else None
                content_list = []
                if data_url:
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
                # If there is text/caption, add as separate dict
                if msg.text:
                    content_list.append({
                        "type": "text",
                        "text": msg.text
                    })
                content = content_list
            elif msg.media_type == "audio":
                content_list = []
                audio_processed = False
                
                # First check if we have an audio_id in raw field
                if msg.is_outgoing and msg.raw and msg.raw.get('audio_id'):
                    audio_id = msg.raw['audio_id']
                    # For assistant messages, we include the audio_id as text since OpenAI doesn't accept audio references
                    # in assistant messages
                    content = msg.text or ""
                    if content == "**Voice Message**":
                        content = ""  # Don't include the default voice message text
                # If no audio_id and we have media file, process it as before
                elif msg.media and multimodal:
                    # Convert audio to mp3 using pydub before base64 encoding
                    try:
                        msg.media.open('rb')
                        data = msg.media.read()
                        msg.media.seek(0)
                        import os
                        orig_ext = os.path.splitext(msg.media.name)[1][1:] or 'wav'
                        
                        # Handle oga extension for pydub
                        format_ext = orig_ext
                        if format_ext == 'oga':
                            format_ext = 'ogg'

                        audio = AudioSegment.from_file(io.BytesIO(data), format=format_ext)
                        mp3_io = io.BytesIO()
                        audio.export(mp3_io, format='mp3')
                        mp3_data = mp3_io.getvalue()
                        b64 = base64.b64encode(mp3_data).decode('ascii')
                        content_list = []
                        if msg.text and msg.text != "**Voice Message**":
                            content_list.append({
                                "type": "text",
                                "text": msg.text
                            })
                        content_list.append({
                            "type": "input_audio",
                            "input_audio": {"data": b64, "format": "mp3"}
                        })
                        content = content_list
                        audio_processed = True
                    except Exception as e:
                        # Re-enable for debugging if needed
                        # print(f"DEBUG: Could not process audio file for message {msg.id}. Error: {e}")
                        content = msg.text or ""  # Fallback to text
                else:
                    content = msg.text or ""
            elif msg.media_type == "html" and msg.html:
                content = msg.html
            else:
                content = msg.text or ""
            d = {"role": role, "content": content}
            return d

        messages = []
        if mode == "chat":
            qs = self.chat.messages.order_by("timestamp")
            idx = list(qs.values_list("id", flat=True)).index(self.id)
            start = max(0, idx - depth + 1)
            selected = list(qs[start:idx+1])
            for m in selected:
                messages.append(msg_to_dict(m))
        elif mode == "thread":
            chain = []
            cur = self
            for _ in range(depth):
                if not cur:
                    break
                chain.append(cur)
                cur = cur.reply_to_message
            for m in reversed(chain):
                messages.append(msg_to_dict(m))
        else:
            raise ValueError(f"Unknown mode: {mode}")
        if system_instruction:
            messages = [{"role": "system", "content": system_instruction}] + messages
        return messages

    def reply_using_llm(self, model: str, depth=10, mode="chat", system_instruction=None, multimodal=True, user=None, voice="alloy", **kwargs):
        """
        Wrapper: Calls as_llm_chat, OpenAI ChatCompletion API, and reply_with.
        - model: OpenAI model string
        - depth, mode, system_instruction, multimodal: passed to as_llm_chat
        - user: Django user for reply_with
        - voice: voice name for audio response (default 'alloy')
        - kwargs: extra params for OpenAI API
        Returns: The Message object created by reply_with
        """
        # Prepare messages for LLM
        messages = self.as_llm_chat(depth=depth, mode=mode, system_instruction=system_instruction, multimodal=multimodal)
        # Determine if we need to request audio response
        openai_kwargs = dict(kwargs)
        if multimodal and self.media_type == "audio":
            openai_kwargs["modalities"] = ["text", "audio"]
            openai_kwargs["audio"] = {"voice": voice, "format": "opus"}
        # Call OpenAI ChatCompletion API
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            **openai_kwargs
        )
        # Get the LLM's reply (assume first choice)
        llm_msg = response.choices[0].message
        # Prepare reply dict
        reply_dict = None
        # If the LLM returns a list of content blocks (OpenAI-style)
        content = getattr(llm_msg, 'content', None)
        if isinstance(content, list):
            # Check for audio or image blocks
            for block in content:
                if block.get("type") == "input_audio":
                    audio_data = block["input_audio"]["data"]
                    ext = block["input_audio"].get("format", "wav")
                    audio_file_name = f"media/{uuid.uuid4()}.{ext}"
                    with open(audio_file_name, "wb") as f:
                        f.write(base64.b64decode(audio_data))
                    reply_dict = {
                        "type": "audio",
                        "file_path": audio_file_name,
                        "text": ""
                    }
                elif block.get("type") == "image_url":
                    url = block["image_url"]["url"]
                    m = re.match(r"data:(.*?);base64,(.*)", url)
                    if m:
                        mime, b64data = m.groups()
                        ext = mime.split("/")[-1]
                        image_file_name = f"media/{uuid.uuid4()}.{ext}"
                        with open(image_file_name, "wb") as f:
                            f.write(base64.b64decode(b64data))
                        reply_dict = {
                            "type": "image",
                            "file_path": image_file_name,
                            "text": ""
                        }
                elif block.get("type") == "text":
                    if reply_dict is None:
                        reply_dict = {"type": "text", "text": block["text"]}
                    else:
                        reply_dict["text"] = block["text"]
        # Handle OpenAI SDK audio id structure with base64 data and transcript
        elif hasattr(llm_msg, 'audio') and llm_msg.audio and hasattr(llm_msg.audio, 'data'):
            audio_data = llm_msg.audio.data
            transcript = getattr(llm_msg.audio, 'transcript', '')
            audio_id = getattr(llm_msg.audio, 'id', None)
            audio_file_name = f"media/{uuid.uuid4()}.ogg"
            wav_bytes = base64.b64decode(audio_data)
            with open(audio_file_name, "wb") as f:
                f.write(wav_bytes)
            reply_dict = {"type": "audio", "file_path": audio_file_name, "audio_id": audio_id}
            if transcript:
                reply_dict["text"] = transcript
        elif self.platform == 'Email':
            reply_dict = {'html': llm_msg.content}
        else:
            reply_dict = {'type': 'text', 'text': llm_msg.content}
        # Reply using reply_with
        return self.reply_with(reply_dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self) -> str:
        return f"{self.platform}:{self.chat.name}->{self.sender_name}: {self.text}"


class EmailInlineImage(models.Model):
    file = DedupFileField(upload_to='email_inline_images/', hash_field='hash')
    email_message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='inline_images', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    content_id = models.CharField(max_length=255, blank=True, null=True, help_text='Content-ID for cid: references in HTML')
    hash = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text='SHA256 hash of file for deduplication')

    def delete(self, *args, **kwargs):
        only_delete_file_if_unused(self, 'file', 'hash')
        super().delete(*args, **kwargs)

    def get_short_id(self):
        # Use base62 encoding of PK for short URLs
        import string
        chars = string.digits + string.ascii_letters
        n = self.pk
        s = ''
        if n == 0:
            return chars[0]
        while n > 0:
            n, r = divmod(n, 62)
            s = chars[r] + s
        return s
