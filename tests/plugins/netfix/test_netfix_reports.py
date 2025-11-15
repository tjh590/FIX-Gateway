import time


def test_report_subscription_push(plugin):
    """
    Subscribe to a report and verify the server pushes a "#q" frame
    including extended fields beyond the legacy 7-field @q reply.
    """
    # Subscribe with a short period (server maintenance runs ~1 Hz)
    plugin.sock.sendall("@QAOA;200\n".encode())
    res = plugin.sock.recv(1024).decode()
    assert res == "@QAOA\n"

    # Wait up to ~3 seconds for a push frame
    deadline = time.time() + 3.0
    buf = ""
    got = None
    while time.time() < deadline and not got:
        try:
            chunk = plugin.sock.recv(4096).decode()
        except Exception:
            # Socket has a timeout; keep waiting until deadline
            continue
        buf += chunk
        # Parse complete lines
        lines = buf.split("\n")
        # Keep any unfinished line in buffer
        buf = lines[-1]
        for line in lines[:-1]:
            if line.startswith("#qAOA;"):
                got = line
                break

    assert got is not None, "Did not receive periodic #qAOA push"

    parts = got.split(";")
    # First token is '#qAOA'; expect 13 additional fields after it:
    # 7 base report fields + 6 extended fields = 13; total parts = 14
    assert parts[0].startswith("#qAOA"), got
    assert len(parts) == 14, f"Unexpected field count: {len(parts)} in: {got}"

    # The last field should be samples count (string integer; may be '0')
    assert parts[-1].isdigit(), f"samples field not integer: {parts[-1]}"

    # Clean up subscription
    plugin.sock.sendall("@UQAOA\n".encode())
    res = plugin.sock.recv(1024).decode()
    assert res == "@UQAOA\n"


def test_report_rate_stats(plugin, database):
    """
    Write AOA at a controlled rate and verify extended rate fields
    (min/max/avg/stdev, samples, last_writer) are populated and sensible.
    """
    # Subscribe; server pushes about once per second
    plugin.sock.sendall("@QAOA;200\n".encode())
    res = plugin.sock.recv(1024).decode()
    assert res == "@QAOA\n"

    # Generate ~20 updates at ~10 Hz for AOA with a known writer id
    writer = "pytest-writer"
    start = time.time()
    value = 0.0
    for _ in range(20):
        value += 1.0
        database.write("AOA", value, writer)
        time.sleep(0.1)
    duration = time.time() - start

    # Wait up to 5 seconds for a push frame that includes enough samples
    deadline = time.time() + 5.0
    buf = ""
    got = None
    while time.time() < deadline and not got:
        try:
            chunk = plugin.sock.recv(4096).decode()
        except Exception:
            continue
        buf += chunk
        lines = buf.split("\n")
        buf = lines[-1]
        for line in lines[:-1]:
            if line.startswith("#qAOA;"):
                parts = line.split(";")
                # Ensure structure (token + 13 fields)
                if len(parts) == 14:
                    # samples must be an int and at least ~10
                    try:
                        samples = int(parts[13])
                    except ValueError:
                        continue
                    if samples >= 10:
                        got = parts
                        break

    assert got is not None, "Did not receive #qAOA with sufficient samples"

    # Indices per server format: 8..13 are extended fields
    last_writer = got[8]
    rmin = got[9]
    rmax = got[10]
    ravg = got[11]
    rstdev = got[12]
    samples = int(got[13])

    # Validate fields are populated
    assert last_writer == writer
    assert rmin != "" and rmax != "" and ravg != "" and rstdev != ""

    # Convert to floats
    rminf = float(rmin)
    rmaxf = float(rmax)
    ravgf = float(ravg)
    rstdevf = float(rstdev)

    # We aimed for ~10 Hz; allow generous tolerance for scheduler jitter
    assert 5.0 <= rminf <= 20.0
    assert 5.0 <= rmaxf <= 20.0
    assert 8.0 <= ravgf <= 12.0, f"avg {ravgf} out of expected range"
    assert rstdevf >= 0.0
    assert samples >= 10

    # Cleanup
    plugin.sock.sendall("@UQAOA\n".encode())
    res = plugin.sock.recv(1024).decode()
    assert res == "@UQAOA\n"
