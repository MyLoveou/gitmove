//! gitmove v2 core: workspace composition, revisions and audits.
//!
//! Storage engines stay external: `git` and `restic` are invoked as processes
//! (ADR-0003/0004). This crate owns the model and the index only.

pub mod asset;
pub mod contribute;
pub mod audit;
pub mod deps;
pub mod error;
pub mod git;
pub mod json;
pub mod merge;
pub mod paths;
pub mod policy;
pub mod registry;
pub mod revision;
pub mod scan;
pub mod workspace;

pub use error::{CoreError, CoreResult};
