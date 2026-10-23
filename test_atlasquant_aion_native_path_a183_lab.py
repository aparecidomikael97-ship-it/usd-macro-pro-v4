"""A183 RED before correction: real native connection, injected factory misrouting."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from aion_chat.staged_store import OperationScopedSQLiteChatStore


class NativeDeclaredPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.scope=Scope("lab-owner","lab-tenant","lab-workspace")
        self.bound=self.root/"bound.db"
        self.other=self.root/"other.db"
        for p in (self.bound,self.other):
            store=SQLiteChatStore(p);store.close()
        self.handle=OperationScopedSQLiteChatStore(self.bound)
        self.addCleanup(self.handle.close)

    def redirected(self):
        other=self.other
        class Redirect(SQLiteChatStore):
            def __init__(self, requested):
                super().__init__(other)
        return patch("aion_chat.staged_store.SQLiteChatStore",Redirect)

    def test_native_connection_redirected_read_must_be_denied(self):
        with self.redirected():
            with self.assertRaisesRegex(StorageUnavailableError,"NATIVE_DATABASE_PATH"):
                self.handle.list_conversations(self.scope)

    def test_native_connection_redirected_write_must_be_denied(self):
        with self.redirected():
            with self.assertRaisesRegex(StorageUnavailableError,"NATIVE_DATABASE_PATH"):
                self.handle.create_conversation(self.scope)
        with closing(sqlite3.connect(self.other)) as db, db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)

    def test_postcommit_connection_drift_is_unknown_and_latched(self):
        other=self.other
        class AfterCommit(SQLiteChatStore):
            def create_conversation(self,*args,**kw):
                result=super().create_conversation(*args,**kw)
                self.db.close()
                self.db=sqlite3.connect(other)
                return result
        with patch("aion_chat.staged_store.SQLiteChatStore",AfterCommit):
            with self.assertRaisesRegex(StorageUnavailableError,"OUTCOME_UNKNOWN"):
                self.handle.create_conversation(self.scope)
        with closing(sqlite3.connect(self.bound)) as db, db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],1)
        with self.assertRaises(StorageUnavailableError):
            self.handle.create_conversation(self.scope)

    def test_same_filename_native_aba_remains_unattested(self):
        import os,shutil
        source=SQLiteChatStore(self.other)
        source.create_conversation(self.scope,title="different-native-file")
        source.close()
        saved=self.bound.with_suffix(".saved")
        detached=self.bound.with_suffix(".detached")
        path=self.bound
        other=self.other
        class SameNameABA(SQLiteChatStore):
            def __init__(self,requested):
                path.rename(saved)
                shutil.copyfile(other,path)
                try:
                    super().__init__(requested)
                    self.db.execute("PRAGMA journal_mode=DELETE")
                    path.rename(detached)
                    saved.rename(path)
                except BaseException:
                    self.close()
                    if path.exists():path.unlink()
                    if saved.exists():saved.rename(path)
                    raise
        if os.name=="nt":
            # Windows may deny rename of SQLite's open native file. This is
            # an OS denial, not a portable guarantee or a skipped assertion.
            try:
                with patch("aion_chat.staged_store.SQLiteChatStore",SameNameABA):
                    result=self.handle.list_conversations(self.scope)
            except (OSError,StorageUnavailableError):
                print("A183_NATIVE_SAME_NAME_ABA=OS_OR_FACADE_DENIED")
                return
        else:
            with patch("aion_chat.staged_store.SQLiteChatStore",SameNameABA):
                result=self.handle.list_conversations(self.scope)
        self.assertEqual([c.title for c in result.items],["different-native-file"])
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)
        print("A183_NATIVE_SAME_NAME_ABA=WRONG_FILE_READ_PATH_CHECK_PASSED")

    def test_same_filename_native_aba_write_can_commit_before_alarm(self):
        import os,shutil
        path=self.bound;other=self.other
        saved=path.with_suffix(".saved");detached=path.with_suffix(".detached")
        class SameNameABA(SQLiteChatStore):
            def __init__(self,requested):
                path.rename(saved);shutil.copyfile(other,path)
                try:
                    super().__init__(requested)
                    self.db.execute("PRAGMA journal_mode=DELETE")
                    path.rename(detached);saved.rename(path)
                except BaseException:
                    self.close()
                    if path.exists():path.unlink()
                    if saved.exists():saved.rename(path)
                    raise
        try:
            with patch("aion_chat.staged_store.SQLiteChatStore",SameNameABA):
                self.handle.create_conversation(self.scope)
        except OSError:
            if os.name!="nt":raise
            print("A183_NATIVE_SAME_NAME_ABA_WRITE=OS_DENIED")
            return
        except sqlite3.OperationalError as exc:
            self.assertEqual(getattr(exc,"sqlite_errorname",""),"SQLITE_READONLY_DBMOVED")
            with closing(sqlite3.connect(detached)) as db, db:
                self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)
            print("A183_NATIVE_SAME_NAME_ABA_WRITE=SQLITE_READONLY_DBMOVED")
            return
        except StorageUnavailableError:
            pass  # UNKNOWN after commit is not proof that write was prevented.
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)
        with closing(sqlite3.connect(detached)) as db, db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],1)
        print("A183_NATIVE_SAME_NAME_ABA_WRITE=DETACHED_FILE_COMMITTED_NOT_PREVENTED")


if __name__=="__main__":
    unittest.main(verbosity=2)

