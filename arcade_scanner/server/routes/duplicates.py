import json
import os

def _get_deps():
    from arcade_scanner.server.api_handler import (
        _dup_mgr, db, user_db, MAX_REQUEST_SIZE, 
        background_duplicate_scan, clear_duplicate_cache
    )
    from arcade_scanner.security import is_path_allowed
    return _dup_mgr, db, user_db, MAX_REQUEST_SIZE, background_duplicate_scan, clear_duplicate_cache, is_path_allowed

def handle_get(handler) -> bool:
    path = handler.path
    if path == "/api/duplicates/status":
        _dup_mgr, _, _, _, _, _, _ = _get_deps()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(_dup_mgr.get_state()).encode("utf-8"))
        return True

    if path == "/api/duplicates" or path == "/api/duplicates/":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            _dup_mgr, _, _, _, _, _, _ = _get_deps()
            cache = _dup_mgr.cache
            groups_data = cache if cache is not None else []
            total_groups = len(groups_data)
            total_videos = sum(1 for g in groups_data if g.get("media_type") == "video")
            total_images = sum(1 for g in groups_data if g.get("media_type") == "image")
            potential_savings = sum(g.get("potential_savings_mb", 0) for g in groups_data)
            
            response = {
                "summary": {
                    "total_groups": total_groups,
                    "video_groups": total_videos,
                    "image_groups": total_images,
                    "potential_savings_mb": potential_savings,
                    "scan_run": cache is not None
                },
                "groups": groups_data
            }
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            print(f"❌ Error returning duplicates: {e}")
            handler.send_error(500, str(e))
        return True
    
    return False

def handle_post(handler) -> bool:
    path = handler.path
    if path == "/api/duplicates/scan":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True

        _dup_mgr, _, user_db, MAX_REQUEST_SIZE, background_duplicate_scan, _, _ = _get_deps()

        if _dup_mgr.get_state()["is_running"]:
            handler.send_error(409, "Scan already in progress")
            return True

        batch_offset = 0
        content_length = int(handler.headers.get("Content-Length", 0))
        if content_length > 0 and content_length <= MAX_REQUEST_SIZE:
            try:
                body = handler.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)
                batch_offset = int(data.get("batch_offset", 0))
            except (ValueError, json.JSONDecodeError) as e:
                print(f"⚠️ Could not parse duplicate scan body: {e}")
                pass 

        u = user_db.get_user(user_name)
        user_targets = None
        if u and u.data.scan_targets:
            user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]

        import threading
        t = threading.Thread(target=background_duplicate_scan, args=(user_targets, batch_offset))
        t.daemon = True
        t.start()
        
        handler.send_response(202)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"status": "started", "batch_offset": batch_offset}).encode("utf-8"))
        return True

    if path == "/api/duplicates/delete":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            _, db, _, MAX_REQUEST_SIZE, _, _, is_path_allowed = _get_deps()
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length > MAX_REQUEST_SIZE:
                handler.send_error(413, "Request too large")
                return True
            
            body = handler.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            paths_to_delete = data.get("paths", [])
            
            if not paths_to_delete:
                handler.send_error(400, "No paths provided")
                return True
            
            deleted = []
            failed = []
            total_freed_mb = 0.0
            
            for p in paths_to_delete:
                try:
                    abs_path = os.path.abspath(p)
                    if not is_path_allowed(abs_path):
                        failed.append({"path": p, "error": "Path not allowed"})
                        continue
                    if os.path.exists(abs_path):
                        size_mb = os.path.getsize(abs_path) / (1024 * 1024)
                        os.remove(abs_path)
                        db.remove(abs_path)
                        deleted.append(abs_path)
                        total_freed_mb += size_mb
                        print(f"🗑️ Deleted duplicate: {os.path.basename(abs_path)} ({size_mb:.1f} MB)")
                    else:
                        failed.append({"path": p, "error": "File not found"})
                except Exception as e:
                    failed.append({"path": p, "error": str(e)})
            
            if deleted:
                db.save()
            
            response = {
                "success": True,
                "deleted": deleted,
                "failed": failed,
                "freed_mb": round(total_freed_mb, 2),
                "freed_gb": round(total_freed_mb / 1024, 2),
            }
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(response).encode("utf-8"))
            print(f"✅ Deleted {len(deleted)} duplicates, freed {total_freed_mb:.1f} MB")
        except json.JSONDecodeError:
            handler.send_error(400, "Invalid JSON")
        except Exception as e:
            print(f"❌ Error deleting duplicates: {e}")
            handler.send_error(500, str(e))
        return True

    if path == "/api/bulk_delete":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            _, db, _, MAX_REQUEST_SIZE, _, _, is_path_allowed = _get_deps()
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length > MAX_REQUEST_SIZE:
                handler.send_error(413, "Request too large")
                return True
            body = handler.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            paths_to_delete = data.get("paths", [])
            
            if not paths_to_delete:
                handler.send_error(400, "No paths provided")
                return True
            
            deleted = []
            failed = []
            
            for p in paths_to_delete:
                try:
                    abs_path = os.path.abspath(p)
                    if not is_path_allowed(abs_path):
                        failed.append({"path": p, "error": "Path not allowed"})
                        continue
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        db.remove(abs_path)
                        deleted.append(abs_path)
                        print(f"🗑️ Bulk Deleted: {os.path.basename(abs_path)}")
                    else:
                        db.remove(abs_path)
                        failed.append({"path": p, "error": "File not found"})
                except Exception as e:
                    failed.append({"path": p, "error": str(e)})
            
            if deleted:
                db.save()
            response = {"success": True, "deleted": deleted, "failed": failed}
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(response).encode("utf-8"))
            print(f"✅ Bulk Deleted {len(deleted)} files")
        except json.JSONDecodeError:
            handler.send_error(400, "Invalid JSON")
        except Exception as e:
            print(f"❌ Error in bulk delete: {e}")
            handler.send_error(500, str(e))
        return True

    if path == "/api/duplicates/clear":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        _, _, _, _, _, clear_duplicate_cache, _ = _get_deps()
        clear_duplicate_cache()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"status": "cleared"}).encode("utf-8"))
        return True

    return False
