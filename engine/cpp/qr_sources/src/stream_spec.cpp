#include "qr_sources/stream_spec.hpp"

#include <string>

namespace qr::sources {
namespace {

constexpr const char* kGateSite = "qr_sources::gate_schema";
constexpr const char* kDoorSite = "qr_sources::read_pinned_column";
constexpr const char* kFormSite = "qr_sources::resolve_form";

std::string column_label(std::string_view stream, std::string_view name, std::size_t leaf) {
  std::string out(stream);
  out += ".";
  out += name;
  out += " (leaf ";
  out += std::to_string(leaf);
  out += ")";
  return out;
}

}  // namespace

const char* column_role_name(ColumnRole role) noexcept {
  switch (role) {
    case ColumnRole::TimestampMs: return "TIMESTAMP_MS";
    case ColumnRole::Int: return "INT";
    case ColumnRole::Price: return "PRICE";
    case ColumnRole::Strike: return "STRIKE";
    case ColumnRole::Date: return "DATE";
    case ColumnRole::Text: return "TEXT";
    case ColumnRole::Float: return "FLOAT";
  }
  return "UNKNOWN_ROLE";
}

const char* column_form_name(ColumnForm form) noexcept {
  switch (form) {
    case ColumnForm::TimestampMsI64: return "TIMESTAMP_MS_I64";
    case ColumnForm::IntI32: return "INT_I32";
    case ColumnForm::IntI64: return "INT_I64";
    case ColumnForm::CentI32: return "CENT_I32";
    case ColumnForm::CentI64: return "CENT_I64";
    case ColumnForm::MillI32: return "MILL_I32";
    case ColumnForm::DollarF64: return "DOLLAR_F64";
    case ColumnForm::DateI32: return "DATE_I32";
    case ColumnForm::DateText: return "DATE_TEXT";
    case ColumnForm::TextUtf8: return "TEXT_UTF8";
    case ColumnForm::FloatF64: return "FLOAT_F64";
  }
  return "UNKNOWN_FORM";
}

const char* forbid_reason_name(ForbidReason reason) noexcept {
  switch (reason) {
    case ForbidReason::NeverRead: return "NEVER_READ";
    case ForbidReason::DecodeRefused: return "DECODE_REFUSED";
    case ForbidReason::HardRefused: return "HARD_REFUSED";
  }
  return "UNKNOWN_REASON";
}

std::size_t SpecView::slot_of(std::size_t leaf) const noexcept {
  for (std::size_t slot = 0; slot < projection_.size(); ++slot) {
    if (projection_[slot] == leaf) {
      return slot;
    }
  }
  return projection_.size();
}

bool SpecView::projects(std::size_t leaf) const noexcept {
  return slot_of(leaf) < projection_.size();
}

const ForbiddenColumn* SpecView::forbids(std::size_t leaf) const noexcept {
  for (const ForbiddenColumn& walled : forbidden_) {
    if (walled.leaf == leaf) {
      return &walled;
    }
  }
  return nullptr;
}

std::size_t SpecView::leaf_of_name(std::string_view name) const noexcept {
  for (std::size_t leaf = 0; leaf < names_.size(); ++leaf) {
    if (names_[leaf] == name) {
      return leaf;
    }
  }
  return names_.size();
}

std::span<const ColumnForm> stock_quote_forms(SourceProfile profile) noexcept {
  switch (profile) {
    case SourceProfile::CentInt32:
      return std::span<const ColumnForm>(kStockQuoteFormsCentInt32);
    case SourceProfile::DollarFloat64:
      return std::span<const ColumnForm>(kStockQuoteFormsDollarFloat64);
  }
  return {};
}

FileExpected<ColumnForm> resolve_form(const parquet::File& file, std::size_t leaf, ColumnRole role,
                                      std::string_view stream) {
  const std::vector<parquet::LeafColumn>& leaves = file.leaves();
  if (leaf >= leaves.size()) {
    return parquet::refuse_file<ColumnForm>(
        RefusalCode::SCHEMA_MISMATCH, kFormSite, "projected leaf is past the file's schema",
        file.path(), std::string(stream), static_cast<std::int64_t>(leaf));
  }
  const parquet::LeafColumn& column = leaves[leaf];
  const auto refuse = [&](const char* what) {
    std::string detail = column_label(stream, column.name, leaf);
    detail += " is ";
    detail += parquet::leaf_type_name(column.type);
    detail += "/";
    detail += parquet::leaf_converted_name(column.converted);
    detail += column.logical_timestamp ? "/LOGICAL_TIMESTAMP" : "";
    detail += ", not an admitted form of role ";
    detail += column_role_name(role);
    return parquet::refuse_file<ColumnForm>(RefusalCode::SCHEMA_MISMATCH, kFormSite, what,
                                            file.path(), std::move(detail),
                                            static_cast<std::int64_t>(leaf));
  };

  switch (role) {
    case ColumnRole::TimestampMs:
      // Frame B on the tape: an INT64 leaf carrying a parquet LogicalType
      // TIMESTAMP. The reference demands arrow Timestamp(Millisecond, None)
      // (`mod.rs:420-438`), which is the same pin one layer up.
      if (column.type == LeafType::INT64 && column.logical_timestamp &&
          column.converted == LeafConverted::NONE) {
        return ColumnForm::TimestampMsI64;
      }
      return refuse("timestamp column is not a naive millisecond INT64");
    case ColumnRole::Int:
      if (column.converted == LeafConverted::NONE) {
        if (column.type == LeafType::INT32) {
          return ColumnForm::IntI32;
        }
        if (column.type == LeafType::INT64 && !column.logical_timestamp) {
          return ColumnForm::IntI64;
        }
      }
      return refuse("integer column is not an admitted integer type");
    case ColumnRole::Price:
      if (column.converted == LeafConverted::NONE) {
        if (column.type == LeafType::INT32) {
          return ColumnForm::CentI32;
        }
        if (column.type == LeafType::INT64 && !column.logical_timestamp) {
          return ColumnForm::CentI64;
        }
        if (column.type == LeafType::DOUBLE) {
          return ColumnForm::DollarF64;
        }
      }
      return refuse("price column is not an admitted price type");
    case ColumnRole::Strike:
      if (column.converted == LeafConverted::NONE) {
        if (column.type == LeafType::INT32) {
          return ColumnForm::MillI32;
        }
        if (column.type == LeafType::DOUBLE) {
          return ColumnForm::DollarF64;
        }
      }
      return refuse("strike column is not an admitted strike type");
    case ColumnRole::Date:
      if (column.type == LeafType::INT32 && column.converted == LeafConverted::DATE) {
        return ColumnForm::DateI32;
      }
      if (column.type == LeafType::BYTE_ARRAY && column.converted == LeafConverted::UTF8) {
        return ColumnForm::DateText;
      }
      return refuse("date column is neither a DATE ordinal nor UTF-8 text");
    case ColumnRole::Text:
      if (column.type == LeafType::BYTE_ARRAY && column.converted == LeafConverted::UTF8) {
        return ColumnForm::TextUtf8;
      }
      return refuse("text column is not UTF-8");
    case ColumnRole::Float:
      if (column.type == LeafType::DOUBLE && column.converted == LeafConverted::NONE) {
        return ColumnForm::FloatF64;
      }
      return refuse("real-valued column is not a DOUBLE");
  }
  return refuse("unknown column role");
}

FileExpected<std::vector<ColumnForm>> gate_schema(const SpecView& spec, const parquet::File& file,
                                                  std::span<const ColumnForm> pinned) {
  using Result = std::vector<ColumnForm>;
  const std::vector<parquet::LeafColumn>& leaves = file.leaves();

  // 1. the column COUNT.
  if (leaves.size() != spec.names().size()) {
    std::string detail(spec.stream());
    detail += ": file has ";
    detail += std::to_string(leaves.size());
    detail += " columns, this reader pins ";
    detail += std::to_string(spec.names().size());
    return parquet::refuse_file<Result>(RefusalCode::SCHEMA_MISMATCH, kGateSite,
                                        "column count is not the pinned one", file.path(),
                                        std::move(detail),
                                        static_cast<std::int64_t>(leaves.size()));
  }

  // 2. every column NAME, in order — including the ones never decoded.
  for (std::size_t leaf = 0; leaf < leaves.size(); ++leaf) {
    if (leaves[leaf].name != spec.names()[leaf]) {
      std::string detail(spec.stream());
      detail += ": column ";
      detail += std::to_string(leaf);
      detail += " is \"";
      detail += leaves[leaf].name;
      detail += "\", pinned as \"";
      detail += std::string(spec.names()[leaf]);
      detail += "\"";
      return parquet::refuse_file<Result>(RefusalCode::SCHEMA_MISMATCH, kGateSite,
                                          "column name is not the pinned one", file.path(),
                                          std::move(detail), static_cast<std::int64_t>(leaf));
    }
  }

  // 3. the FORM of every projected column.
  if (!pinned.empty() && pinned.size() != spec.projection().size()) {
    return parquet::refuse_file<Result>(RefusalCode::CONFIG, kGateSite,
                                        "pinned form vector does not cover the projection",
                                        file.path(), std::string(spec.stream()),
                                        static_cast<std::int64_t>(pinned.size()));
  }
  Result forms;
  forms.reserve(spec.projection().size());
  for (std::size_t slot = 0; slot < spec.projection().size(); ++slot) {
    const std::size_t leaf = spec.projection()[slot];
    FileExpected<ColumnForm> resolved = resolve_form(file, leaf, spec.roles()[slot], spec.stream());
    if (!resolved.has_value()) {
      return FileExpected<Result>::refuse(resolved.error());
    }
    if (!pinned.empty() && resolved.value() != pinned[slot]) {
      std::string detail = column_label(spec.stream(), spec.names()[leaf], leaf);
      detail += " is ";
      detail += column_form_name(resolved.value());
      detail += ", this session's declared profile pins ";
      detail += column_form_name(pinned[slot]);
      return parquet::refuse_file<Result>(RefusalCode::SCHEMA_MISMATCH, kGateSite,
                                          "column form disagrees with the declared profile",
                                          file.path(), std::move(detail),
                                          static_cast<std::int64_t>(leaf));
    }
    forms.push_back(resolved.value());
  }
  return forms;
}

FileExpected<std::int64_t> read_pinned_column(const SpecView& spec, const parquet::File& file,
                                              std::size_t row_group, std::size_t leaf,
                                              DecodeWorkspace& workspace, ColumnData& out) {
  if (leaf >= spec.names().size()) {
    std::string detail(spec.stream());
    detail += ": leaf ";
    detail += std::to_string(leaf);
    detail += " is outside the pinned schema";
    return parquet::refuse_file<std::int64_t>(RefusalCode::SCHEMA_MISMATCH, kDoorSite,
                                              "leaf index is outside the pinned schema",
                                              file.path(), std::move(detail),
                                              static_cast<std::int64_t>(leaf));
  }
  if (const ForbiddenColumn* walled = spec.forbids(leaf); walled != nullptr) {
    std::string detail = column_label(spec.stream(), spec.names()[leaf], leaf);
    detail += " is ";
    detail += forbid_reason_name(walled->reason);
    detail += " by FINAL_PLAN APPENDIX B; no payload byte of it is read";
    return parquet::refuse_file<std::int64_t>(RefusalCode::COLUMN_FORBIDDEN, kDoorSite,
                                              "the data-usage map forbids this column",
                                              file.path(), std::move(detail),
                                              static_cast<std::int64_t>(leaf));
  }
  if (!spec.projects(leaf)) {
    std::string detail = column_label(spec.stream(), spec.names()[leaf], leaf);
    detail += " is not projected by this stream";
    return parquet::refuse_file<std::int64_t>(RefusalCode::SCHEMA_MISMATCH, kDoorSite,
                                              "column is outside the projection", file.path(),
                                              std::move(detail), static_cast<std::int64_t>(leaf));
  }
  return file.read_column(row_group, leaf, workspace, out);
}

FileExpected<std::int64_t> read_pinned_column_named(const SpecView& spec,
                                                    const parquet::File& file,
                                                    std::size_t row_group, std::string_view name,
                                                    DecodeWorkspace& workspace, ColumnData& out) {
  const std::size_t leaf = spec.leaf_of_name(name);
  if (leaf >= spec.names().size()) {
    std::string detail(spec.stream());
    detail += ": no column named \"";
    detail += std::string(name);
    detail += "\"";
    return parquet::refuse_file<std::int64_t>(RefusalCode::SCHEMA_MISMATCH, kDoorSite,
                                              "unknown column name", file.path(),
                                              std::move(detail));
  }
  return read_pinned_column(spec, file, row_group, leaf, workspace, out);
}

}  // namespace qr::sources
