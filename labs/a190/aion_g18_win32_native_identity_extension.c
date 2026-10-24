/* A190 G18 — isolated Windows native identity of the EXACT Python sqlite3.Connection.
 * LAB ONLY. This is a loadable C extension and must NEVER be installed, loaded
 * or auto-loaded in the AION runtime. It has no external trust root.
 */
#include "sqlite3ext.h"
SQLITE_EXTENSION_INIT1

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

static void aion_g18_win32_identity(sqlite3_context *ctx, int argc, sqlite3_value **argv) {
    sqlite3 *db = sqlite3_context_db_handle(ctx);
    (void)argv;
    if (argc != 0 || db == 0) {
        sqlite3_result_error(ctx, "G18_BAD_CONNECTION_DENY", -1);
        return;
    }
#ifdef _WIN32
    HANDLE handle = NULL;
    BY_HANDLE_FILE_INFORMATION info;
    char identity[64];
    int rc = sqlite3_file_control(db, "main", SQLITE_FCNTL_WIN32_GET_HANDLE, &handle);
    if (rc != SQLITE_OK || handle == NULL || handle == INVALID_HANDLE_VALUE) {
        sqlite3_result_error(ctx, "G18_WIN32_NATIVE_HANDLE_UNSUPPORTED_DENY", -1);
        return;
    }
    if (!GetFileInformationByHandle(handle, &info)) {
        sqlite3_result_error(ctx, "G18_WIN32_FILE_INFO_UNAVAILABLE_DENY", -1);
        return;
    }
    sqlite3_snprintf((int)sizeof(identity), identity, "%08x:%08x:%08x",
                     (unsigned int)info.dwVolumeSerialNumber,
                     (unsigned int)info.nFileIndexHigh,
                     (unsigned int)info.nFileIndexLow);
    sqlite3_result_text(ctx, identity, -1, SQLITE_TRANSIENT);
#else
    sqlite3_result_error(ctx, "G18_WINDOWS_ONLY_DENY", -1);
#endif
}

#ifdef _WIN32
__declspec(dllexport)
#endif
int sqlite3_aiong18_init(sqlite3 *db, char **err, const sqlite3_api_routines *api) {
    (void)err;
    SQLITE_EXTENSION_INIT2(api);
    return sqlite3_create_function_v2(db, "aion_lab_win32_native_identity", 0,
        SQLITE_UTF8 | SQLITE_DIRECTONLY, NULL, aion_g18_win32_identity,
        NULL, NULL, NULL);
}
