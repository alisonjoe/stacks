import random
from pathlib import Path # 记得导入


def orchestrate_download(d, input_string, prefer_mirror=None, resume_attempts=3, filename=None, links=None):
    """Download a file from Anna's Archive.

    Args:
        d: Downloader instance
        input_string: MD5 hash or URL
        prefer_mirror: Preferred mirror to try first
        resume_attempts: Number of resume attempts
        filename: Pre-fetched filename (optional, will fetch if not provided)
        links: Pre-fetched download links (optional, will fetch if not provided)

    Returns: (success, used_fast_download, filepath)
    """
    md5 = d.extract_md5(input_string)
    if not md5:
        d.logger.error(f"Could not extract MD5 from: {input_string}")
        return False, False, None

    d.logger.info(f"Downloading: {md5}")

    # Fetch download info if not provided
    if filename is None or links is None:
        filename, links = d.get_download_links(md5)

    # ---------------- [修改开始] ----------------
    # 严格检查元数据文件名
    if filename and filename != "Unknown":
        # 定义白名单
        valid_extensions = {'.epub', '.mobi', '.azw3'}
        file_ext = Path(filename).suffix.lower()

        # 如果文件后缀存在，但不在白名单里 (比如是 .pdf)
        if file_ext and file_ext not in valid_extensions:
            d.logger.error(f"ABORTING: MD5 {md5} metadata says it is '{file_ext}', but we only want epub/mobi/azw3.")
            return False, False, None
    # ---------------- [修改结束] ----------------
    # Try fast download first
    if d.fast_download_enabled and d.fast_download_key:
        if hasattr(d, 'status_callback'):
            d.status_callback("Trying fast download...")

        success, result = d.try_fast_download(md5)

        if success:
            d.logger.info("Using fast download")
            if hasattr(d, 'status_callback'):
                d.status_callback("Downloading via fast download...")

            filepath = d.download_direct(result, title=filename, resume_attempts=resume_attempts, md5=md5)
            if filepath:
                d.logger.info("Fast download successful")
                return True, True, filepath
            else:
                d.logger.warning("Fast download failed, falling back to mirrors")
        else:
            d.logger.info(f"Fast download not available: {result}")


    if not links:
        d.logger.error("No download links found")
        return False, False, None

    d.logger.info(f"Found {len(links)} mirror(s)")


    # Preferred mirror
    if prefer_mirror:
        preferred = [link for link in links if prefer_mirror.lower() in link['domain'].lower()]
        others = [link for link in links if prefer_mirror.lower() not in link['domain'].lower()]
        links = preferred + others
    else:
        # Shuffle to spread load across mirrors (unless user has preference)
        random.shuffle(links)

    # Try each mirror
    for i, mirror_link in enumerate(links):
        mirror_name = mirror_link.get('text', mirror_link.get('domain', 'Unknown'))
        d.logger.info(f"Trying mirror {i+1}/{len(links)}: {mirror_name}")

        if hasattr(d, 'status_callback'):
            d.status_callback(f"Accessing mirror {i+1}/{len(links)}: {mirror_name}")

        filepath = d.download_from_mirror(
            mirror_link['url'],
            mirror_link['type'],
            md5,
            title=filename,
            resume_attempts=resume_attempts
        )

        if filepath:
            d.logger.info("Download successful")
            if hasattr(d, 'status_callback'):
                d.status_callback("Verifying download...")
            return True, False, filepath
        else:
            d.logger.warning(f"Mirror {mirror_name} failed")
            if i < len(links) - 1:
                d.logger.info("Trying next mirror...")
                if hasattr(d, 'status_callback'):
                    d.status_callback("Mirror failed, trying next mirror...")

    d.logger.error("All mirrors failed")
    return False, False, None
