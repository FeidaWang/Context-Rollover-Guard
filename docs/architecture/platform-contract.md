# Additional platform and client contracts

Current implementation uses POSIX fcntl locking, descriptor-relative O_NOFOLLOW
opens, owner/mode checks, same-filesystem atomic installation, file fsync and parent
directory fsync. The normalized reader reuses that descriptor-pinned regular-file
boundary and refuses devices/FIFOs/sockets before opening their content.

Native Windows remains **unsupported**. This macOS session supplies no native
Windows runner, ACL/reparse-point implementation or native fault-injection evidence.
A WSL/Linux success cannot qualify as a native Windows result. This expansion task
is explicitly deferred on that evidence, not silently marked complete.

Before porting, supply a reviewed Windows backend for owner-only ACLs, sharing and
lock timeout rules, replace/link behavior, FlushFileBuffers and durable directory
installation, long paths, case-folded identity and reparse-point rejection. Run
process-kill tests at every journal/install/commit boundary on the actual filesystem.
Do not replace fcntl alone and claim equivalent durability. Network filesystems and
unsupported clients must fail closed.

Desktop internal bridges remain experimental. Complete answer capture, current
workspace/permission binding, accepted-operation evidence and exact response bytes
must be independently observed before claiming recovery support. Otherwise use
observation-only mode; no internal endpoint or authentication extraction is added.
