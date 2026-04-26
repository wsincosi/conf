function yoyo::local_import_paths(
  Array[String] $local_imports,
  String $inbox_base,
  String $host,
) >> Hash[String, String] {
  $local_imports.reduce({}) |Hash[String, String] $memo, String $type| {
    $memo + { $type => "${inbox_base}/${host}/${type}" }
  }
}
