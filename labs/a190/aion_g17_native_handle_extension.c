/* A190 G17 — experimental bridge into the EXACT Python stdlib SQLite handle.
 *
 * LAB only. Native loadable extensions execute arbitrary code, so this module
 * must NEVER be auto-loaded, installed into production, or treated as a trust
 * root. The test explicitly enables loading for its private connection only
 * and disables it immediately after loading the verified lab artifact.
 *
 * We use the documented SQLite extension API (sqlite3ext.h + API table).
 * The function asks the connection that is evaluating its SQL for the VFS
 * HAS_MOVED status. This is distinct from probing process fds or re-opening
 * a database by pathname. A supported unmoved status is only a local
 * observation, not owner proof, content authenticity or rollback custody.
 */
#include "sqlite3ext.h"
SQLITE_EXTENSION_INIT1

static void aion_g17_has_moved(
    sqlite3_context *context, int argc, sqlite3_value **argv
) {
    sqlite3 *db = sqlite3_context_db_handle(context);
    int moved = -1;
    int rc;
    (void)argv;
    if (argc != 0 || db == 0) {
        sqlite3_result_error(context, "G17_BAD_NATIVE_CONNECTION", -1);
        return;
    }
    rc = sqlite3_file_control(db, "main", SQLITE_FCNTL_HAS_MOVED, &moved);
    if (rc != SQLITE_OK) {
        sqlite3_result_error(context, "G17_HAS_MOVED_UNSUPPORTED_DENY", -1);
        return;
    }
    if (moved != 0 && moved != 1) {
        sqlite3_result_error(context, "G17_HAS_MOVED_INVALID_DENY", -1);
        return;
    }
    sqlite3_result_int(context, moved);
}

#ifdef _WIN32
__declspec(dllexport)
#endif
int sqlite3_aiong17_init(
    sqlite3 *db, char **error_message, const sqlite3_api_routines *api
) {
    (void)error_message;
    SQLITE_EXTENSION_INIT2(api);
    return sqlite3_create_function_v2(
        db, "aion_lab_native_has_moved", 0,
        SQLITE_UTF8 | SQLITE_DIRECTONLY, 0,
        aion_g17_has_moved, 0, 0, 0
    );
}
