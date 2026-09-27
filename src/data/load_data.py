from pathlib import Path
from time import perf_counter

import pandas as pd
import psutil
import yaml


# Xác định thư mục repository từ vị trí src/data/load_data.py.
ROOT = Path(__file__).resolve().parents[2]


def read_config():
    """Đọc cấu hình dùng chung cho loader và bước clean sau này."""
    path = ROOT / "config/data_config.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_file(raw_dir, pattern, year):
    """Tìm đúng một file TXT đã giải nén của từng năm."""
    filename = pattern.format(year=year)
    matches = list(raw_dir.rglob(filename))

    if len(matches) != 1:
        raise ValueError(
            f"{filename}: cần đúng 1 file, tìm thấy {len(matches)}."
        )

    return matches[0]


def iter_chunks(path, spec, config):
    """Trả từng chunk để clean_data.py xử lý tiếp, không gom vào RAM."""
    # Kiểm tra layout dòng đầu; kiểm tra toàn bộ cấu trúc thuộc task raw QC.
    with path.open(encoding=config["encoding"]) as file:
        first_line = file.readline()

    if not first_line:
        raise ValueError(f"File rỗng: {path.name}")

    column_count = len(first_line.rstrip("\r\n").split("|"))
    if column_count != spec["total_columns"]:
        raise ValueError(
            f"{path.name}: dòng đầu có {column_count} cột, "
            f"layout yêu cầu {spec['total_columns']}."
        )

    # Chỉ đọc các cột cần thiết và giữ mã như 01/03/09 ở dạng chuỗi.
    with pd.read_csv(
        path,
        sep="|",
        header=None,
        usecols=list(spec["columns"]),
        dtype="string",
        keep_default_na=False,
        encoding=config["encoding"],
        chunksize=config["chunk_size"],
        skip_blank_lines=False,
        on_bad_lines="error",
    ) as reader:
        for chunk in reader:
            df = chunk.rename(columns=spec["columns"]).copy()

            # Giữ giá trị raw trước khi trim/chuyển kiểu.
            for col in spec["dates"] + spec["numbers"]:
                df[f"{col}_raw"] = df[col]

            for col in spec["columns"].values():
                df[col] = df[col].str.strip().replace("", pd.NA)

            if df["loan_id"].isna().any():
                raise ValueError(f"{path.name}: có dòng thiếu loan_id.")

            # YYYYMM được biểu diễn bằng ngày đầu tháng.
            for col in spec["dates"]:
                df[col] = pd.to_datetime(
                    df[col], format="%Y%m", errors="raise"
                )

            for col in spec["numbers"]:
                df[col] = pd.to_numeric(
                    df[col], errors="raise"
                ).astype("Float64")

            # Thông tin để truy ngược về file và dòng dữ liệu gốc.
            df["source_file"] = path.name
            df["source_row"] = df.index + 1

            # Chưa đổi 999/9999, lọc cohort, tạo event hoặc tính analysis_time.
            yield df


def main():
    """Chạy kiểm tra loader và đo thời gian/RAM cho từng file."""
    config = read_config()

    raw_dir = Path(config["raw_dir"])
    if not raw_dir.is_absolute():
        raw_dir = ROOT / raw_dir

    report_dir = ROOT / config["report_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)

    process = psutil.Process()
    benchmark = []

    for year in config["source_years"]:
        for kind in ["origination", "performance"]:
            spec = config[kind]
            path = find_file(raw_dir, spec["filename"], year)

            start = perf_counter()
            rows = chunks = 0
            max_ram = process.memory_info().rss / 1024**2

            for df in iter_chunks(path, spec, config):
                rows += len(df)
                chunks += 1

                # RAM tiến trình tại thời điểm nhận từng chunk.
                ram = process.memory_info().rss / 1024**2
                max_ram = max(max_ram, ram)

                if chunks % 10 == 0:
                    print(f"{path.name}: đã đọc {rows:,} dòng.", flush=True)

                # Không giữ lại chunk sau khi đo.
                del df

            if rows == 0:
                raise ValueError(f"{path.name}: không có dữ liệu.")

            seconds = perf_counter() - start
            benchmark.append({
                "source_year": year,
                "dataset": kind,
                "file": path.name,
                "rows_read": rows,
                "chunks": chunks,
                "seconds": round(seconds, 2),
                "max_sampled_rss_mb": round(max_ram, 2),
            })

            # Lưu tiến độ benchmark sau mỗi file thành công.
            pd.DataFrame(benchmark).to_csv(
                report_dir / "ingestion_benchmark.csv", index=False
            )

            print(
                f"Xong {path.name}: {rows:,} dòng, "
                f"{seconds:.1f} giây, RAM đo được tối đa {max_ram:.1f} MB.",
                flush=True,
            )

    print("Hoàn thành kiểm tra loader.")


if __name__ == "__main__":
    main()