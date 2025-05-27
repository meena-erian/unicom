from unicom.services.email.save_email_message import save_email_message
from imapclient import IMAPClient, SEEN
import imaplib
import time
import logging

logger = logging.getLogger(__name__)


def listen_to_IMAP(channel):
    """
    Connects to the IMAP server defined in channel.config and listens via IDLE.
    Fetches new messages and hands them off to save_email_message().
    This runs indefinitely, with automatic reconnects on failure.
    """
    email_address = channel.config['EMAIL_ADDRESS']
    password      = channel.config['EMAIL_PASSWORD']
    imap_conf     = channel.config['IMAP']
    host          = imap_conf['host']
    port          = imap_conf['port']
    use_ssl       = imap_conf['use_ssl']

    logger.info(f"Channel {channel.pk}: Starting IMAP listener for {email_address} at {host}:{port} (SSL={use_ssl})")

    while True:
        try:
            with IMAPClient(host, port=port, ssl=use_ssl) as server:
                server.login(email_address, password)
                server.select_folder('INBOX')
                logger.info(f"Channel {channel.pk}: Connected to {host}:{port}, entering IDLE…")

                while True:
                    idle_tag = None
                    try:
                        # server.idle()
                        idle_tag = server.idle()
                        # check every 240s; will let us gracefully send DONE before timeout
                        responses = server.idle_check(timeout=60)
                    except (imaplib.IMAP4.abort, ConnectionResetError, OSError) as e:
                        logger.warning(f"Channel {channel.pk}: IMAP idle lost: {e}")
                        break
                    finally:
                        # only send DONE if IDLE was entered
                        if idle_tag:
                            try:
                                server.idle_done()
                            except Exception:
                                pass

                    if not responses:
                        continue

                    uids = server.search(['UNSEEN'])
                    for uid in uids:
                        try:
                            resp = server.fetch(uid, ['BODY.PEEK[]'])
                            raw = resp[uid][b'BODY[]']
                            msg = save_email_message(channel, raw)
                            logger.info(f"Channel {channel.pk}: Saved email {msg.id} (uid={uid})")
                            server.add_flags(uid, [SEEN])
                        except Exception:
                            logger.exception(f"Channel {channel.pk}: Failed to process UID {uid}")

        except Exception:
            logger.exception(f"Channel {channel.pk}: Fatal IMAP error, reconnecting in 30s…")
            time.sleep(30)