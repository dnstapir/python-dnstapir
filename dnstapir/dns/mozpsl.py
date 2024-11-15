import io
from typing import Self

import httpx


class TrieNode:
    """ "Storage class for Trie"""

    def __init__(self) -> None:
        self.count = 0
        self.icann: bool | None = None
        self.children: dict[str, Self] = {}


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def __repr__(self) -> str:
        """Print full Trie structure"""

        def recur(node: TrieNode, indent: str) -> str:
            return "".join(
                indent + key + (f" {child.count}" if child.count else "") + recur(child, indent + " - ")
                for key, child in node.children.items()
            )

        return recur(self.root, "\n")

    def insert(self, array: list[str], nlbl: int, icann: bool) -> None:
        """Add data to Trie"""
        node = self.root
        for x in array:
            if x in node.children:
                node = node.children[x]
            else:
                child = TrieNode()
                node.children[x] = child
                node = child
        node.count = nlbl
        node.icann = icann

    def search(self, key: list[str]) -> tuple[int, int]:
        """Search Trie"""
        current = self.root
        for label in key:
            if current.icann:
                core = current.count
            else:
                pcore = current.count
            if label not in current.children:
                if current.count != 0:
                    break
                else:
                    raise KeyError
            current = current.children[label]
        if pcore == core:
            pcore = 0
        return (core, pcore)


class PublicSuffixList:
    """Mozilla Public Suffix List"""

    def __init__(self) -> None:
        self.trie = Trie()

    def load_psl_url(self, url: str) -> None:
        """Load PSL from URL"""
        response = httpx.get(
            url,
            headers={
                "Accept-Encoding": "gzip",
            },
        )
        response.raise_for_status()
        self.load_psl(io.StringIO(response.text))

    def load_psl(self, stream: io.StringIO) -> None:
        """Load PSL from stream"""
        icann = False
        for line in stream:
            line = line.rstrip()

            if "===BEGIN ICANN DOMAINS===" in line:
                # Mark ICANN domains
                icann = True
            elif "===BEGIN PRIVATE DOMAINS===" in line:
                # Mark PRIVATE domains
                icann = False

            if (line.strip() == "") or (line[0] == "/"):
                # Remove empty or comment lines
                continue

            # Set number of labels in core domain
            labels = len(line.split(".")) + 1

            # Wildcards
            if line[0] == "*":
                line = line[2:]

            # Exclusions... .ck and .jp, just stop
            if line[0] == "!":
                line = line[1:]
                labels -= 2

            # Convert from Unicode
            lbls = line.encode("idna").decode().split(".")

            # Store reversed
            lbls.reverse()

            # Insert into Trie
            self.trie.insert(lbls, labels, icann)

    def coredomain(self, domain: str) -> tuple[str, str]:
        """Find ICANN and private name cut-off for domain"""
        if not domain:
            raise ValueError
        try:
            domain = domain.rstrip(".")
        except AttributeError as exc:
            raise ValueError from exc
        lbls = domain.split(".")
        lbls.reverse()
        c, p = self.trie.search(lbls)
        core = lbls[0:c]
        core.reverse()
        pcore = lbls[0:p]
        pcore.reverse()
        return (".".join(core), ".".join(pcore))

    def rdomain(self, rdomain: str) -> tuple[str, str]:
        """Find ICANN and private name cut-off for domain, reverse order process"""
        lbls = rdomain.split(".")
        c, p = self.trie.search(lbls)
        return (".".join(lbls[0:c]), ".".join(lbls[0:p]))
