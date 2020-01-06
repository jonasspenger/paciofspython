import sys

sys.path.append("paciofs")

import unittest.mock
import unittest
import logging
import time
import os
import tamperproofbroadcast
import blockchain
import paciofs

logging.disable(logging.CRITICAL)


class TestPacioFS(unittest.TestCase):
    def setUp(self):
        n_blockchains = 1
        self.blockchains = []
        self.broadcasts = []
        self.filesystems = []

        b = blockchain.Blockchain()
        b._create()
        b._start()
        self.blockchains.append(b)

        keypairs = [b._create_funded_keypair() for _ in range(n_blockchains)]

        for i in range(n_blockchains - 1):
            b2 = blockchain.Blockchain(chainname=b.getinfo()["nodeaddress"])
            b2._start()
            self.blockchains.append(b2)

        for keypair, b in zip(keypairs, self.blockchains):
            bc = tamperproofbroadcast.TamperProofBroadcast(
                keypair[0], keypair[1], keypair[2]
            )
            filesystem = paciofs.PacioFS()
            bc._register_southbound(b)
            bc._register_northbound(filesystem)
            bc._start()
            self.broadcasts.append(bc)
            filesystem._register_southbound(bc)
            filesystem._start()
            self.filesystems.append(filesystem)

    def tearDown(self):
        for fs in self.filesystems:
            fs._stop()
        for bc in self.broadcasts:
            bc._stop()
        for b in self.blockchains:
            b._stop()

    def test_verify(self):
        for i, fs in enumerate(self.filesystems):
            dirname = str(i) + str(i)
            filename = str(i)
            payload = str(i).encode()
            fs.create(filename, 0o777)
            fh = fs.open(filename, os.O_WRONLY)
            fs.write(filename, payload, 0, fh)
            fs.release(filename, fh)
            fs.mkdir(dirname, 755)

        # wait for changes to propagate
        time.sleep(60)

        # assert that FS is verified
        for i, fs in enumerate(self.filesystems):
            self.assertTrue(fs._verify())

        # unauthorized change of file system
        for i, fs in enumerate(self.filesystems):
            dirname = str(i) + str(i)
            filename = str(i)
            payload = "unauthorizedchange".encode()
            fh = fs.filesystem.open(filename, os.O_WRONLY)
            fs.filesystem.write(filename, payload, 0, fh)
            fs.filesystem.release(filename, fh)

        # assert that FS not verified
        for i, fs in enumerate(self.filesystems):
            self.assertFalse(fs._verify())

    def test_paciofs(self):
        for i, fs in enumerate(self.filesystems):
            dirname = str(i) + str(i)
            filename = str(i)
            payload = str(i).encode()
            fs.create(filename, 0o777)
            fh = fs.open(filename, os.O_WRONLY)
            fs.write(filename, payload, 0, fh)
            fs.release(filename, fh)
            fs.mkdir(dirname, 755)

        # wait for changes to propagate
        time.sleep(60)

        for i, fs in enumerate(self.filesystems):
            for j, _ in enumerate(self.filesystems):
                dirname = str(j) + str(j)
                filename = str(j)
                payload = str(j).encode()
                self.assertTrue(filename in list(fs.readdir("/", None)))
                fh = fs.open(filename, os.O_RDONLY)
                self.assertEqual(payload, fs.read(filename, 1024, 0, fh))
                fs.release(filename, fh)
                self.assertTrue(dirname in list(fs.readdir("/", None)))
