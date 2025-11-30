cd ~/git-repos

for d in */ ; do
  if [ -d "$d/.git" ]; then
    echo "===== $d ====="
    (
      cd "$d" && \
      git pull --ff-only || \
      echo "⚠️  git pull --ff-only failed in $d"
    )
    echo
  fi
done
