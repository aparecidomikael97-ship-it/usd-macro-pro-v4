/* A185 LAB, not production. Native SQLite VFS, statement-level epoch guard,
 * default-VFS explicit bypass, and WAL writing vs main-file-only policy.
 * Compile: cc -std=c11 -Wall -Wextra -Werror -O0 sqlite_vfs_epoch_wal_lab.c -lsqlite3 -o a185_followup
 */
#define _GNU_SOURCE
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static sqlite3_vfs observed, *base_vfs;
static int main_opens=0, wal_opens=0;
static int main_writes=0, wal_writes=0, denied_main_writes=0, denied_wal_writes=0;
static int deny_main_write=0, deny_wal_write=0;

typedef struct InstrumentedFile {
    sqlite3_file public_file;
    sqlite3_file *actual;
    int kind;
} InstrumentedFile;
static InstrumentedFile *wrap(sqlite3_file *f){return (InstrumentedFile *)f;}
static const sqlite3_io_methods *ops(sqlite3_file *f){return wrap(f)->actual->pMethods;}
static int fclose_io(sqlite3_file *f){return ops(f)->xClose(wrap(f)->actual);}
static int fread_io(sqlite3_file *f,void *buf,int n,sqlite3_int64 o){return ops(f)->xRead(wrap(f)->actual,buf,n,o);}
static int fwrite_io(sqlite3_file *f,const void *buf,int n,sqlite3_int64 o){
    if (wrap(f)->kind & SQLITE_OPEN_MAIN_DB) {
        main_writes++;
        if(deny_main_write){denied_main_writes++;return SQLITE_IOERR_WRITE;}
    }
    if (wrap(f)->kind & SQLITE_OPEN_WAL) {
        wal_writes++;
        if(deny_wal_write){denied_wal_writes++;return SQLITE_IOERR_WRITE;}
    }
    return ops(f)->xWrite(wrap(f)->actual,buf,n,o);
}
static int ftruncate_io(sqlite3_file *f,sqlite3_int64 s){return ops(f)->xTruncate(wrap(f)->actual,s);}
static int fsync_io(sqlite3_file *f,int flags){return ops(f)->xSync(wrap(f)->actual,flags);}
static int fsize_io(sqlite3_file *f,sqlite3_int64 *s){return ops(f)->xFileSize(wrap(f)->actual,s);}
static int flock_io(sqlite3_file *f,int n){return ops(f)->xLock(wrap(f)->actual,n);}
static int funlock_io(sqlite3_file *f,int n){return ops(f)->xUnlock(wrap(f)->actual,n);}
static int fcheck_io(sqlite3_file *f,int *x){return ops(f)->xCheckReservedLock(wrap(f)->actual,x);}
static int fcontrol_io(sqlite3_file *f,int n,void *x){return ops(f)->xFileControl(wrap(f)->actual,n,x);}
static int fsector_io(sqlite3_file *f){return ops(f)->xSectorSize(wrap(f)->actual);}
static int fdev_io(sqlite3_file *f){return ops(f)->xDeviceCharacteristics(wrap(f)->actual);}
static int fshmmap_io(sqlite3_file *f,int p,int n,int extend,void volatile **out){
    const sqlite3_io_methods *m=ops(f);
    return m->iVersion>=2&&m->xShmMap ? m->xShmMap(wrap(f)->actual,p,n,extend,out):SQLITE_IOERR;
}
static int fshmlock_io(sqlite3_file *f,int p,int n,int flags){
    const sqlite3_io_methods *m=ops(f);
    return m->iVersion>=2&&m->xShmLock ? m->xShmLock(wrap(f)->actual,p,n,flags):SQLITE_IOERR;
}
static void fshmbarrier_io(sqlite3_file *f){const sqlite3_io_methods *m=ops(f);if(m->iVersion>=2&&m->xShmBarrier)m->xShmBarrier(wrap(f)->actual);}
static int fshmunmap_io(sqlite3_file *f,int drop){
    const sqlite3_io_methods *m=ops(f);return m->iVersion>=2&&m->xShmUnmap ? m->xShmUnmap(wrap(f)->actual,drop):SQLITE_IOERR;
}
static int ffetch_io(sqlite3_file *f,sqlite3_int64 o,int n,void **out){
    *out=NULL;const sqlite3_io_methods *m=ops(f);return m->iVersion>=3&&m->xFetch ? m->xFetch(wrap(f)->actual,o,n,out):SQLITE_OK;
}
static int funfetch_io(sqlite3_file *f,sqlite3_int64 o,void *p){
    const sqlite3_io_methods *m=ops(f);return m->iVersion>=3&&m->xUnfetch ? m->xUnfetch(wrap(f)->actual,o,p):SQLITE_OK;
}
static const sqlite3_io_methods wrapped_methods={
    .iVersion=3,.xClose=fclose_io,.xRead=fread_io,.xWrite=fwrite_io,.xTruncate=ftruncate_io,
    .xSync=fsync_io,.xFileSize=fsize_io,.xLock=flock_io,.xUnlock=funlock_io,
    .xCheckReservedLock=fcheck_io,.xFileControl=fcontrol_io,.xSectorSize=fsector_io,
    .xDeviceCharacteristics=fdev_io,.xShmMap=fshmmap_io,.xShmLock=fshmlock_io,
    .xShmBarrier=fshmbarrier_io,.xShmUnmap=fshmunmap_io,.xFetch=ffetch_io,.xUnfetch=funfetch_io
};
static int observed_open(sqlite3_vfs *v,const char *name,sqlite3_file *out,int flags,int *outflags){
    InstrumentedFile *w=(InstrumentedFile *)out;
    memset(w,0,sizeof(*w));w->actual=(sqlite3_file *)((char *)out+sizeof(*w));w->kind=flags;
    sqlite3_vfs *delegate=(sqlite3_vfs *)v->pAppData;
    int rc=delegate->xOpen(delegate,name,w->actual,flags,outflags);
    if(rc!=SQLITE_OK)return rc;
    w->public_file.pMethods=&wrapped_methods;
    if(flags&SQLITE_OPEN_MAIN_DB)main_opens++;
    if(flags&SQLITE_OPEN_WAL)wal_opens++;
    return SQLITE_OK;
}
static int exec(sqlite3 *db,const char *sql){
    char *err=NULL;int rc=sqlite3_exec(db,sql,NULL,NULL,&err);
    if(err){fprintf(stderr,"SQL[%s] rc=%d (%s)\n",sql,rc,err);sqlite3_free(err);}
    return rc;
}
static sqlite3 *open_db(const char *p,const char *vfs){
    sqlite3 *db=NULL;
    int rc=sqlite3_open_v2(p,&db,SQLITE_OPEN_READWRITE|SQLITE_OPEN_CREATE,vfs);
    if(rc!=SQLITE_OK){fprintf(stderr,"OPEN %s rc=%d\n",vfs?vfs:"DEFAULT",rc);if(db)sqlite3_close(db);return NULL;}
    return db;
}
typedef struct EpochGuard {int captured,authoritative,enabled,callbacks;} EpochGuard;
static int must_reject(EpochGuard *g){return !g->enabled || g->captured!=g->authoritative;}
static int check_progress(void *arg){EpochGuard *g=(EpochGuard *)arg;g->callbacks++;return must_reject(g);}
static int select_one(sqlite3_stmt *st){sqlite3_reset(st);int rc=sqlite3_step(st);sqlite3_reset(st);return rc;}
int main(void){
    int failures=0;
    char work[]="/tmp/a185-guard-wal-XXXXXX";
    if(!mkdtemp(work))return 2;
    char path[512],walpath[512],sidepath[532];
    snprintf(path,sizeof(path),"%s/cache.sqlite",work);
    snprintf(walpath,sizeof(walpath),"%s/wal.sqlite",work);
    base_vfs=sqlite3_vfs_find(NULL);
    if(!base_vfs)return 2;
    observed=*base_vfs;observed.zName="a185_epoch_vfs";observed.pAppData=base_vfs;
    observed.szOsFile=(int)(sizeof(InstrumentedFile)+base_vfs->szOsFile);
    observed.xOpen=observed_open;
    if(sqlite3_vfs_register(&observed,1)!=SQLITE_OK)return 2;
    sqlite3 *db=open_db(path,NULL); /* new default is the instrumented VFS */
    if(!db)return 2;
    sqlite3_file *f=NULL;
    int native=sqlite3_file_control(db,"main",SQLITE_FCNTL_FILE_POINTER,&f)==SQLITE_OK && f && f->pMethods==&wrapped_methods;
    if(exec(db,"CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t VALUES(1,'a');")!=SQLITE_OK)return 2;
    sqlite3_stmt *st=NULL;
    if(sqlite3_prepare_v2(db,"SELECT v FROM t WHERE id=1",-1,&st,NULL)!=SQLITE_OK)return 2;
    int before=select_one(st);
    EpochGuard policy={.captured=1,.authoritative=1,.enabled=1,.callbacks=0};
    sqlite3_progress_handler(db,1,check_progress,&policy);
    int warm=select_one(st);
    policy.authoritative=2; /* revocation AFTER cached page AND prepared statement */
    int revoked=select_one(st);
    int guarded_callbacks=policy.callbacks;
    policy.authoritative=1;
    int restored=select_one(st);
    printf("NATIVE_VFS_ON_DEFAULT=%s PREPARED_WARM_RC=%d REVOKED_CACHED_RC=%d PROGRESS_CALLBACKS=%d RESTORED_RC=%d\n",
           native?"YES":"NO",warm,revoked,guarded_callbacks,restored);
    if(!native || before!=SQLITE_ROW || warm!=SQLITE_ROW || revoked!=SQLITE_INTERRUPT || restored!=SQLITE_ROW || guarded_callbacks<1)failures++;
    sqlite3_finalize(st);sqlite3_progress_handler(db,0,NULL,NULL);sqlite3_close(db);
    /* Explicitly naming original VFS bypasses a VFS-only gate despite new default. */
    deny_main_write=1;
    sqlite3 *bypass=open_db(path,base_vfs->zName);
    int bypass_rc=bypass ? exec(bypass,"UPDATE t SET v='unguarded' WHERE id=1;") : SQLITE_ERROR;
    if(bypass)sqlite3_close(bypass);
    printf("EXPLICIT_BASE_VFS_BYPASS_RC=%d (SQLITE_OK 0 proves local coverage gap)\n",bypass_rc);
    if(bypass_rc!=SQLITE_OK)failures++;
    deny_main_write=0;
    /* New DB in WAL mode: writes often go to WAL, not MAIN_DB. */
    sqlite3 *wdb=open_db(walpath,"a185_epoch_vfs");
    if(!wdb)return 2;
    if(exec(wdb,"PRAGMA journal_mode=WAL; CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT);")!=SQLITE_OK)return 2;
    int wal_seen=wal_opens;
    int wal_before=wal_writes, main_before=main_writes;
    deny_main_write=1;
    int main_only_rc=exec(wdb,"INSERT INTO t VALUES(1,'allowed_by_wal');");
    int main_delta=main_writes-main_before,wal_delta=wal_writes-wal_before;
    deny_main_write=0;
    printf("WAL_MODE_MAIN_ONLY_DENY_INSERT_RC=%d WAL_XWRITE_DELTA=%d MAIN_XWRITE_DELTA=%d WAL_OPEN=%d\n",
           main_only_rc,wal_delta,main_delta,wal_seen);
    if(main_only_rc!=SQLITE_OK || wal_seen<1 || wal_delta<1)failures++;
    deny_wal_write=1;
    int denied_rc=exec(wdb,"INSERT INTO t VALUES(2,'must_deny');");
    deny_wal_write=0;
    printf("WAL_XWRITE_DENY_INSERT_RC=%d DENIED_WAL_WRITES=%d\n",denied_rc,denied_wal_writes);
    if(denied_rc==SQLITE_OK || denied_wal_writes<1)failures++;
    sqlite3_close(wdb);
    sqlite3_vfs_register(base_vfs,1);sqlite3_vfs_unregister(&observed);
    unlink(path);unlink(walpath);
    snprintf(sidepath,sizeof(sidepath),"%s-wal",walpath);unlink(sidepath);
    snprintf(sidepath,sizeof(sidepath),"%s-shm",walpath);unlink(sidepath);
    rmdir(work);
    printf("A185_LAB_RESULT=%s SECURITY_STATUS=INCOMPLETE_STDLIB_BYPASS_AND_EXTERNAL_EPOCH_UNATTESTED\n",failures?"FAIL":"PASS_NEGATIVE_CONTROLS");
    return failures?1:0;
}
