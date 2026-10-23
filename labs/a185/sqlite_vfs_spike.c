/* A185 LAB ONLY: public SQLite VFS wrapper. No Python internals, no production use.
 * Purpose: demonstrate that REAL sqlite3_file IO can be intercepted, and that
 * cached SELECTs can avoid xRead entirely. Not a full fail-closed security VFS.
 * Build: cc -std=c11 -Wall -Wextra -Werror sqlite_vfs_spike.c -lsqlite3 -o a185_vfs_spike
 */
#define _GNU_SOURCE
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static sqlite3_vfs g_vfs;
static sqlite3_vfs *g_base;
static int g_block_read=0, g_block_write=0;
static int g_reads=0, g_writes=0, g_denied_reads=0, g_denied_writes=0;
static int g_main_open=0, g_wal_open=0, g_journal_open=0;

typedef struct GateFile {
  sqlite3_file base;
  sqlite3_file *inner;
  int flags;
  /* Native sqlite3_file of inherited VFS follows this struct in szOsFile allocation. */
} GateFile;
static GateFile *GF(sqlite3_file *f) {return (GateFile*)f;}
static const sqlite3_io_methods *IM(sqlite3_file *f) {return GF(f)->inner->pMethods;}
static int gate_close(sqlite3_file *f){return IM(f)->xClose(GF(f)->inner);}
static int gate_read(sqlite3_file *f,void *buf,int n,sqlite3_int64 o){
  if(GF(f)->flags & SQLITE_OPEN_MAIN_DB){
    g_reads++;
    if(g_block_read){g_denied_reads++;return SQLITE_IOERR_READ;}
  }
  return IM(f)->xRead(GF(f)->inner,buf,n,o);
}
static int gate_write(sqlite3_file *f,const void *buf,int n,sqlite3_int64 o){
  if(GF(f)->flags & SQLITE_OPEN_MAIN_DB){
    g_writes++;
    if(g_block_write){g_denied_writes++;return SQLITE_IOERR_WRITE;}
  }
  return IM(f)->xWrite(GF(f)->inner,buf,n,o);
}
static int gate_trunc(sqlite3_file *f,sqlite3_int64 s){return IM(f)->xTruncate(GF(f)->inner,s);}
static int gate_sync(sqlite3_file *f,int fl){return IM(f)->xSync(GF(f)->inner,fl);}
static int gate_filesize(sqlite3_file *f,sqlite3_int64 *s){return IM(f)->xFileSize(GF(f)->inner,s);}
static int gate_lock(sqlite3_file *f,int l){return IM(f)->xLock(GF(f)->inner,l);}
static int gate_unlock(sqlite3_file *f,int l){return IM(f)->xUnlock(GF(f)->inner,l);}
static int gate_check(sqlite3_file *f,int *r){return IM(f)->xCheckReservedLock(GF(f)->inner,r);}
static int gate_control(sqlite3_file *f,int o,void *a){return IM(f)->xFileControl(GF(f)->inner,o,a);}
static int gate_sector(sqlite3_file *f){return IM(f)->xSectorSize(GF(f)->inner);}
static int gate_devcap(sqlite3_file *f){return IM(f)->xDeviceCharacteristics(GF(f)->inner);}
static int gate_shmmap(sqlite3_file *f,int i,int n,int b,void volatile **p){
  const sqlite3_io_methods *m=IM(f);return m->iVersion>=2 && m->xShmMap ? m->xShmMap(GF(f)->inner,i,n,b,p) : SQLITE_IOERR;
}
static int gate_shmlock(sqlite3_file *f,int i,int n,int flags){
  const sqlite3_io_methods *m=IM(f);return m->iVersion>=2 && m->xShmLock ? m->xShmLock(GF(f)->inner,i,n,flags) : SQLITE_IOERR;
}
static void gate_shmbarrier(sqlite3_file *f){
  const sqlite3_io_methods *m=IM(f);if(m->iVersion>=2 && m->xShmBarrier)m->xShmBarrier(GF(f)->inner);
}
static int gate_shmunmap(sqlite3_file *f,int d){
  const sqlite3_io_methods *m=IM(f);return m->iVersion>=2 && m->xShmUnmap ? m->xShmUnmap(GF(f)->inner,d) : SQLITE_IOERR;
}
static int gate_fetch(sqlite3_file *f,sqlite3_int64 o,int n,void **p){
  const sqlite3_io_methods *m=IM(f);*p=NULL;
  if(GF(f)->flags & SQLITE_OPEN_MAIN_DB){
    if(g_block_read){g_denied_reads++;return SQLITE_IOERR_READ;}
  }
  return m->iVersion>=3 && m->xFetch ? m->xFetch(GF(f)->inner,o,n,p) : SQLITE_OK;
}
static int gate_unfetch(sqlite3_file *f,sqlite3_int64 o,void *p){
  const sqlite3_io_methods *m=IM(f);return m->iVersion>=3 && m->xUnfetch ? m->xUnfetch(GF(f)->inner,o,p) : SQLITE_OK;
}
static const sqlite3_io_methods gate_methods={
  .iVersion=3, .xClose=gate_close, .xRead=gate_read, .xWrite=gate_write,
  .xTruncate=gate_trunc, .xSync=gate_sync, .xFileSize=gate_filesize,
  .xLock=gate_lock, .xUnlock=gate_unlock, .xCheckReservedLock=gate_check,
  .xFileControl=gate_control, .xSectorSize=gate_sector, .xDeviceCharacteristics=gate_devcap,
  .xShmMap=gate_shmmap, .xShmLock=gate_shmlock, .xShmBarrier=gate_shmbarrier,
  .xShmUnmap=gate_shmunmap, .xFetch=gate_fetch, .xUnfetch=gate_unfetch
};
static int gate_open(sqlite3_vfs *v,const char *name,sqlite3_file *out,int flags,int *outflags){
  GateFile *gf=(GateFile*)out;
  memset(gf,0,sizeof(*gf));
  gf->inner=(sqlite3_file*)((char*)out+sizeof(GateFile));
  gf->flags=flags;
  int rc=((sqlite3_vfs*)v->pAppData)->xOpen((sqlite3_vfs*)v->pAppData,name,gf->inner,flags,outflags);
  if(rc!=SQLITE_OK)return rc;
  if(flags & SQLITE_OPEN_MAIN_DB)g_main_open++;
  if(flags & SQLITE_OPEN_WAL)g_wal_open++;
  if(flags & SQLITE_OPEN_MAIN_JOURNAL)g_journal_open++;
  gf->base.pMethods=&gate_methods;
  return SQLITE_OK;
}
static void must_sql(sqlite3 *db,const char *sql){
  char *err=NULL;int rc=sqlite3_exec(db,sql,NULL,NULL,&err);
  if(rc!=SQLITE_OK){fprintf(stderr,"FATAL_SQL %s rc=%d %s\n",sql,rc,err?err:sqlite3_errmsg(db));sqlite3_free(err);exit(2);}
}
static int select_id(sqlite3_stmt *st,int id){
  sqlite3_reset(st);sqlite3_clear_bindings(st);sqlite3_bind_int(st,1,id);
  int rc=sqlite3_step(st);sqlite3_reset(st);return rc;
}
int main(void){
  char dir[]="/tmp/a185-sqlite-vfs-XXXXXX";
  if(!mkdtemp(dir)){perror("mkdtemp");return 2;}
  char path[512];snprintf(path,sizeof(path),"%s/demo.sqlite",dir);
  sqlite3 *seed=NULL;
  if(sqlite3_open(path,&seed)!=SQLITE_OK)return 2;
  must_sql(seed,"PRAGMA journal_mode=DELETE; CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT NOT NULL); BEGIN;");
  sqlite3_stmt *put=NULL;
  if(sqlite3_prepare_v2(seed,"INSERT INTO t(id,v) VALUES(?,?)",-1,&put,NULL)!=SQLITE_OK)return 2;
  char val[321];memset(val,'X',sizeof(val)-1);val[sizeof(val)-1]=0;
  for(int i=1;i<=10000;i++){
    sqlite3_reset(put);sqlite3_bind_int(put,1,i);sqlite3_bind_text(put,2,val,-1,SQLITE_STATIC);
    if(sqlite3_step(put)!=SQLITE_DONE)return 2;
  }
  sqlite3_finalize(put);must_sql(seed,"COMMIT;");sqlite3_close(seed);
  g_base=sqlite3_vfs_find(NULL);
  if(!g_base){fprintf(stderr,"NO_VFS\n");return 2;}
  g_vfs=*g_base;g_vfs.zName="a185_instrumented";g_vfs.pAppData=g_base;
  g_vfs.szOsFile=(int)(sizeof(GateFile)+g_base->szOsFile);g_vfs.xOpen=gate_open;
  if(sqlite3_vfs_register(&g_vfs,0)!=SQLITE_OK)return 2;
  sqlite3 *db=NULL;
  int rc=sqlite3_open_v2(path,&db,SQLITE_OPEN_READWRITE,"a185_instrumented");
  if(rc!=SQLITE_OK){fprintf(stderr,"GATE_OPEN_FAIL=%d\n",rc);return 2;}
  must_sql(db,"PRAGMA cache_size=20; PRAGMA mmap_size=0;");
  sqlite3_file *native=NULL;
  rc=sqlite3_file_control(db,"main",SQLITE_FCNTL_FILE_POINTER,&native);
  int ptr_seen=rc==SQLITE_OK && native && native->pMethods==&gate_methods;
  printf("NATIVE_HANDLE_SAME_VFS=%s MAIN_OPENS=%d\n",ptr_seen?"YES":"NO",g_main_open);
  sqlite3_stmt *near=NULL,*far=NULL;
  if(sqlite3_prepare_v2(db,"SELECT v FROM t WHERE id=?",-1,&near,NULL)!=SQLITE_OK)return 2;
  if(sqlite3_prepare_v2(db,"SELECT v FROM t WHERE id=?",-1,&far,NULL)!=SQLITE_OK)return 2;
  must_sql(db,"BEGIN;");
  int warm=select_id(near,1);int prior_reads=g_reads;
  g_block_read=1;
  int cached=select_id(near,1);int cached_read_count=g_reads-prior_reads;
  int cold=select_id(far,10000);
  printf("WARM_RC=%d CACHE_AFTER_DENY_RC=%d CACHE_EXTRA_XREAD=%d COLD_AFTER_DENY_RC=%d DENIED_READS=%d\n",
         warm,cached,cached_read_count,cold,g_denied_reads);
  g_block_read=0;sqlite3_finalize(near);sqlite3_finalize(far);
  if(!sqlite3_get_autocommit(db))must_sql(db,"ROLLBACK;");
  g_block_write=1;
  char *err=NULL;
  rc=sqlite3_exec(db,"BEGIN IMMEDIATE; UPDATE t SET v='NOT_ALLOWED' WHERE id=1; COMMIT;",NULL,NULL,&err);
  printf("WRITE_AFTER_DENY_RC=%d DENIED_WRITES=%d MAIN_WRITES=%d JOURNAL_OPENS=%d WAL_OPENS=%d\n",
         rc,g_denied_writes,g_writes,g_journal_open,g_wal_open);
  if(err)sqlite3_free(err);
  int blocked_rc=rc;
  sqlite3_close(db);
  /* RED counterexample: a default-VFS connection is NOT covered by the gate. */
  sqlite3 *unguarded=NULL;
  int default_open=sqlite3_open(path,&unguarded);
  int default_write=SQLITE_ERROR;
  if(default_open==SQLITE_OK){
    default_write=sqlite3_exec(unguarded,"UPDATE t SET v='BYPASS' WHERE id=1",NULL,NULL,NULL);
    sqlite3_close(unguarded);
  }
  printf("DEFAULT_VFS_WHILE_GUARD_DENIES_WRITE_RC=%d (SQLITE_OK=0 is bypass)\n",default_write);
  g_block_write=0;
  sqlite3_vfs_unregister(&g_vfs);
  remove(path);rmdir(dir);
  if(!ptr_seen || warm!=SQLITE_ROW || cached!=SQLITE_ROW || cached_read_count!=0 ||
     cold==SQLITE_ROW || g_denied_reads<1 || blocked_rc==SQLITE_OK ||
     g_denied_writes<1 || default_write!=SQLITE_OK){
    puts("RESULT=FAIL (native wrapper may not enforce the expected IO path)");return 1;
  }
  puts("RESULT=PASS_NATIVE_IO_INTERCEPTION; SECURITY_RESULT=INCOMPLETE_CACHE_AND_DEFAULT_VFS_BYPASSES");
  return 0;
}
