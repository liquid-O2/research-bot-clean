//! Label kernels and query structures for the stage-1 label catalog; design
//! authority `docs/specs/label_kernel_design_v1.md`.

pub mod anchor;
pub mod extrema;
pub mod f_cfa;
pub mod f_ctrl;
pub mod f_dir;
pub mod f_dwell;
pub mod f_ext;
pub mod f_ord;
pub mod f_pass;
pub mod f_prox;
pub mod f_qprim;
pub mod f_rank;
pub mod f_term;
pub mod frame;
pub mod probe;
pub mod regimes;
pub mod scheduler;

pub use anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
pub use extrema::ExtremaTree;
pub use frame::{Breaker, GroupKind, SessionFrame};
