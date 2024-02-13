

import phanas.automount
import phanas.nas

def generate():
    env = phanas.automount.Env()
    nas = phanas.nas.Nas()
    nas2 = phanas.nas.Nas2()
    mnt_alias = "{}_MOUNT_NAS".format(env.linux_username.upper())
    mnt_aliases = list(map(lambda x: "/bin/mount --types cifs //{}/{} {}/{} *".format(nas.host(), x, env.mount_dir_path, x), nas.drives()))
    mnt_aliases = mnt_aliases + list(map(lambda x: "/bin/mount --types cifs //{}/{} {}/{} *".format(nas2.host(), x, env.mount_dir_path, x), nas2.drives()))
    umnt_alias = "{}_UMOUNT_NAS".format(env.linux_username.upper())
    umnt_aliases = list(map(lambda x: "/bin/umount {}/{}".format(env.mount_dir_path, x), nas.drives() + nas2.drives()))

    txt = """
Cmnd_Alias {} = \\
{}
Cmnd_Alias {} = \\
{}

# Allow user {} to mount and umount NAS drives without password
{} ALL=(ALL) NOPASSWD: {}, {}
""".format(mnt_alias, ", \\\n".join(mnt_aliases), umnt_alias, ", \\\n".join(umnt_aliases), env.linux_username, env.linux_username, mnt_alias, umnt_alias)
        
    return txt
