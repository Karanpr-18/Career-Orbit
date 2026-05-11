def load_existing_urls(tracker_path: str = "") -> set:
    from config import TRACKER_CSV_PATH
    if not tracker_path: tracker_path = TRACKER_CSV_PATH
    urls = set()
    if not os.path.exists(tracker_path): return urls
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            content = f.read()
            url_pattern = re.compile(r"https?://[^\s,'\"\r\n]+")
            urls = set(url_pattern.findall(content))
        return urls
    except Exception as e:
        logger.error(f"[Tracker] Failed to load URLs: {e}")
        return urls

def count_successful_sends(tracker_path: str = "") -> int:
    from config import TRACKER_CSV_PATH
    if not tracker_path: tracker_path = TRACKER_CSV_PATH
    if not os.path.exists(tracker_path): return 0
    count = 0
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Find the 'Application Status' column index (usually the last one)
            for row in reader:
                if not row: continue
                # Success statuses: Mailed, Applied, Drafted
                status = row[-1].lower()
                if any(s in status for s in ["mailed", "applied", "drafted"]):
                    count += 1
        return count
    except Exception as e:
        logger.error(f"[Tracker] Failed to count success: {e}")
        return 0
