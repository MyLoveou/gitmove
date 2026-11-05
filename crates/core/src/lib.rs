//! gitmove v2 core: workspace composition, revisions and audits.
//!
//! Storage engines stay external: `git` and `restic` are invoked as processes
//! (ADR-0003/0004). This crate owns the model and the index only.

pub mod audit;
pub mod error;
pub mod git;
pub mod json;
pub mod paths;
pub mod registry;
pub mod revision;
pub mod scan;
pub mod workspace;

pub use error::{CoreError, CoreResult};
