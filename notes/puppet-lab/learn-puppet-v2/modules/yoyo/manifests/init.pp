class yoyo (

  # Name of the concrete service instance, for example "xyz".
  #
  # This comes from Hiera, for example:
  # yoyo::instance_name: 'xyz'
  #
  # Type "String" means this value must be text.
  String $instance_name,

  # Optional list of local import names, for example:
  # ['coffee', 'tea']
  #
  # "Optional[Array[String]]" means:
  # - either an array of strings
  # - or undef (not set at all)
  #
  # If the key is absent in Hiera, this becomes undef.
  Optional[Array[String]] $local_imports = undef,

  # Root directory under which instance directories will be built.
  #
  # For learning/testing we use /tmp so root-owned system paths
  # are not required.
  String $base_dir = '/tmp',

  # Where to write the generated config file.
  String $config_path = '/tmp/yoyo.conf',

  # Hostname segment used in local import paths.
  #
  # Defaults to the current node hostname, but can be overridden
  # during local testing to simulate other hosts.
  String $host = $facts['networking']['hostname'],
) {

  # Build the instance root path.
  #
  # Example if instance_name = xyz:
  #   /tmp/yoyo_xyz
  #
  # "${...}" is Puppet string interpolation.
  # It inserts variable values into a string.
  $instance_root = "${base_dir}/yoyo_${instance_name}"

  # Build the inbox base path.
  #
  # Example:
  #   /tmp/yoyo_xyz/inbox
  $inbox_base = "${instance_root}/inbox"

  # Only do local-import work if the node data actually defines
  # yoyo::local_imports.
  #
  # If local_imports is undef, this whole block is skipped.
  if $local_imports != undef {

    # Ensure the base directory exists before creating the
    # instance-specific directory tree beneath it.
    file { $base_dir:
      ensure => directory,
      mode   => '0755',
    }

    # Convert the local import names into the concrete paths used by
    # both the directory resources below and the rendered config file.
    $local_import_paths = yoyo::local_import_paths(
      $local_imports,
      $inbox_base,
      $host,
    )

    # Ensure the instance root exists, e.g. /tmp/yoyo_xyz
    file { $instance_root:
      ensure => directory,  # path must exist and be a directory
      mode   => '0755',     # standard directory permissions
      require => File[$base_dir],
    }

    # Ensure the inbox directory exists, e.g. /tmp/yoyo_xyz/inbox
    file { $inbox_base:
      ensure  => directory,
      mode    => '0755',

      # "require" creates an ordering dependency.
      # This means Puppet must create $instance_root first.
      require => File[$instance_root],
    }

    # Ensure the host-specific inbox exists, e.g.
    # /tmp/yoyo_xyz/inbox/host-01
    file { "${inbox_base}/${host}":
      ensure  => directory,
      mode    => '0755',
      require => File[$inbox_base],
    }

    # Loop over the hash of import paths and create one directory
    # for each import type.
    #
    # "each" iterates over the hash.
    # |String $type, String $path| means:
    # - $type is the hash key
    # - $path is the hash value
    $local_import_paths.each |String $type, String $path| {

      # Example generated resources:
      # file { '/tmp/yoyo_xyz/inbox/host-01/coffee': ... }
      # file { '/tmp/yoyo_xyz/inbox/host-01/tea': ... }
      file { $path:
        ensure  => directory,
        mode    => '0755',
        require => File["${inbox_base}/${host}"],
      }
    }

    # Render the config file from the ERB template.
    #
    # "template('yoyo/yoyo.conf.erb')" means:
    # load templates/yoyo.conf.erb from the yoyo module,
    # evaluate it, and use the result as file content.
    file { $config_path:
      ensure  => file,  # path must exist as a normal file
      content => template('yoyo/yoyo.conf.erb'),
    }
  }
}
