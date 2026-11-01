//! Directed local file dependencies and relevance scoring.

use petgraph::graphmap::DiGraphMap;

use crate::index::{FileId, Index};
use crate::repo::Repository;

mod scorer;

pub use scorer::GraphScorer;

/// Edges point from an importing or declaring file to its local dependency.
/// Includes possible dependencies across build configurations and optional environments.
#[derive(Debug)]
pub struct Graph {
    /// Directed file dependency edges using IDs from the associated index.
    pub dependencies: DiGraphMap<FileId, ()>,
}

impl Graph {
    /// Builds a graph from the language dependency analyses.
    ///
    /// Includes every indexed file as a node and excludes self-dependency edges.
    pub fn new(index: &Index, repository: &Repository) -> Self {
        let mut dependencies = DiGraphMap::new();

        for (file, _) in index.files.iter() {
            dependencies.add_node(file);
        }

        for language in index.languages.values() {
            for (from, to) in language.resolve_dependencies(index, repository) {
                if from != to {
                    dependencies.add_edge(from, to, ());
                }
            }
        }

        Self { dependencies }
    }

    /// Returns the number of distinct directed dependency edges.
    pub fn edge_count(&self) -> usize {
        self.dependencies.edge_count()
    }

    /// Iterates over the local dependencies of a file.
    ///
    /// Iteration order is unspecified. Unknown IDs produce an empty iterator.
    pub fn neighbors(&self, file: FileId) -> impl Iterator<Item = FileId> + '_ {
        self.dependencies.neighbors(file)
    }
}
