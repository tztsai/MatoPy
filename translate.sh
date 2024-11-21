source_files=$1
target_dir=$2

translate() {
    python main.py "$source_files" -d "$target_dir" -v
}

translate || {
    pip install -r smop/requirements.txt
    translate
}

cp matopy/lib.py "$target_dir/libsmop.py"
find "$target_dir" -name "*.py" -exec 2to3 -x import -w -n {} +
ruff format "$target_dir"
ruff check "$target_dir" --fix