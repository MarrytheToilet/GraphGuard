"""Fixed Kuzu Cypher execution for the deployment Q1--Q4 workload."""

from __future__ import annotations

import gc
import shutil
import tempfile
from pathlib import Path
from typing import Iterable


class KuzuGraph:
    """Ephemeral Kuzu materialization with lossless parameter binding."""

    def __init__(self, edges: Iterable[tuple[str, str, str]]):
        import kuzu

        self._directory = Path(tempfile.mkdtemp(prefix="graphguard-kuzu-"))
        self._database = None
        self.connection = None
        try:
            self._database = kuzu.Database(str(self._directory / "db"))
            self.connection = kuzu.Connection(self._database)
            self.connection.execute(
                "CREATE NODE TABLE Entity(id STRING, PRIMARY KEY(id))"
            )
            self.connection.execute(
                "CREATE REL TABLE Rel(FROM Entity TO Entity, label STRING)"
            )
            typed_edges = sorted(set(edges))
            nodes = sorted(
                {node for s, _, o in typed_edges for node in (s, o)}
            )
            for node in nodes:
                self.connection.execute(
                    "CREATE (e:Entity {id: $id})",
                    parameters={"id": str(node)},
                )
            for subject, relation, obj in typed_edges:
                self.connection.execute(
                    "MATCH (a:Entity {id: $subject}), "
                    "(b:Entity {id: $object}) "
                    "CREATE (a)-[:Rel {label: $relation}]->(b)",
                    parameters={
                        "subject": str(subject),
                        "relation": str(relation),
                        "object": str(obj),
                    },
                )
        except BaseException:
            self.close()
            raise

    def execute(self, query: tuple[str, dict]) -> set:
        family, parameters = query
        connection = self.connection
        if family == "lookup":
            result = connection.execute(
                "MATCH (a:Entity {id:$h})"
                "-[e:Rel {label:$r}]->(b) RETURN DISTINCT b.id",
                parameters={
                    "h": str(parameters["h"]),
                    "r": str(parameters["r"]),
                },
            )
            return {row[0] for row in result}
        if family == "neighbor":
            result = connection.execute(
                "MATCH (a:Entity {id:$h})-[e:Rel]->(b) "
                "RETURN DISTINCT e.label, b.id",
                parameters={"h": str(parameters["h"])},
            )
            return {(row[0], row[1]) for row in result}
        if family == "join":
            result = connection.execute(
                "MATCH (a1:Entity {id:$h1})"
                "-[:Rel {label:$r1}]->(t)<-"
                "[:Rel {label:$r2}]-(a2:Entity {id:$h2}) "
                "RETURN DISTINCT t.id",
                parameters={
                    "h1": str(parameters["h1"]),
                    "r1": str(parameters["r1"]),
                    "h2": str(parameters["h2"]),
                    "r2": str(parameters["r2"]),
                },
            )
            return {row[0] for row in result}
        if family == "twohop":
            result = connection.execute(
                "MATCH (a:Entity {id:$h})"
                "-[:Rel {label:$r1}]->(x)"
                "-[:Rel {label:$r2}]->(t) "
                "RETURN DISTINCT t.id",
                parameters={
                    "h": str(parameters["h"]),
                    "r1": str(parameters["r1"]),
                    "r2": str(parameters["r2"]),
                },
            )
            return {row[0] for row in result}
        raise KeyError(f"unknown deployment query family: {family}")

    def close(self) -> None:
        if getattr(self, "connection", None) is not None:
            del self.connection
        if getattr(self, "_database", None) is not None:
            del self._database
        gc.collect()
        shutil.rmtree(self._directory, ignore_errors=True)

    def __enter__(self) -> "KuzuGraph":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def kuzu_version() -> str:
    import kuzu

    return str(getattr(kuzu, "__version__", "unknown"))
