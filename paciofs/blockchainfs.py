import logging.config
import tempfile
import logging
import inspect
import shutil
import fuse
import rpyc
import os
import blockchainbroadcast
import passthrough
import kvstore
import module

logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.conf"))
logger = logging.getLogger("blockchainfsoperations")

statechangingfunctions = [
    "chmod",
    "chown",
    "create",
    "link",
    "mkdir",
    "mknod",
    "removexattr",
    "rename",
    "rmdir",
    "setxattr",
    "symlink",
    "truncate",
    "unlink",
    "utimens",
    "write",
]


class BlockchainFS(rpyc.Service, fuse.Operations, module.Module):
    def register_broadcast(self, broadcast):
        self.southbound = broadcast

    def _decorator(self, f):
        def _upon_fsapi(*args, **kwargs):
            logger.debug("upon FSAPI: %s", (f.__name__, *args))
            if f.__name__ in statechangingfunctions:
                logger.debug("trigger Broadcast: %s", (f.__name__, *args))
                try:
                    self.southbound.broadcast(message=(f.__name__, *args))
                except Exception as e:
                    logger.error("error: %s" % e)
                return f(*args, **kwargs)
            else:
                return f(*args, **kwargs)

        return _upon_fsapi

    def _upon_deliver(self, pid, txid, msg):
        try:
            self.metadata[msg[1]] = txid
            logger.debug("upon deliver: pid=%s; txid=%s; msg=%s" % (pid, txid, msg))
            if msg[0] == "write":
                fh = self.filesystem.open(msg[1], os.O_WRONLY)
                self.filesystem.write(msg[1], msg[2], msg[3], fh)
                self.filesystem.release(msg[1], fh)
            else:
                getattr(self.filesystem, msg[0])(*msg[1:])
        except Exception as e:
            logger.error("error: %s" % e)

    def __init__(self, volume=None):
        self.volume = volume
        if self.volume == None:
            self.volume = tempfile.mkdtemp()
            self._handle_exit(lambda: shutil.rmtree(self.volume, ignore_errors=True))
        if not os.path.isdir(self.volume) and not os.path.isfile(self.volume):
            os.mkdir(self.volume)
        elif os.path.isfile(self.volume):
            raise Exception("%s is not a valid path" % self.volume)

        logger.info("creating blockchainfilesystem at volume=%s" % (self.volume))
        self.metadata = kvstore.KVStore()
        self.filesystem = passthrough.Passthrough(self.volume)
        for name, method in inspect.getmembers(self.filesystem):
            if name[0] != "_" and method is not None:
                setattr(self, name, self._decorator(method))