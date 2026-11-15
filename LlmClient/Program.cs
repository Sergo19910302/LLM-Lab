using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;

var http = new HttpClient
{
    BaseAddress = new Uri("http://127.0.0.1:8000"),
    Timeout = TimeSpan.FromSeconds(120)
};

string mode = args.Length > 0 ? args[0] : "basic";
switch (mode)
{
    case "basic":    await Basic(); break;
    case "fairness": await Fairness(8, 50); break;
    case "soak":     await Soak(args.Length > 1 ? int.Parse(args[1]) : 30); break;
    case "eval":     await Eval(); break;
    default: Console.WriteLine("Modes: basic | fairness | soak [minutes]"); break;
}

// Keep Windows awake while a test runs
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
static extern uint SetThreadExecutionState(uint flags);

// ---------- shared call ----------
async Task<GenResp> Generate(string prompt, int maxTokens = 64, double temperature = 0.2)
{
    var resp = await http.PostAsJsonAsync("/generate", new { prompt, max_tokens = maxTokens, temperature });
    resp.EnsureSuccessStatusCode();
    return (await resp.Content.ReadFromJsonAsync<GenResp>())!;
}

// ---------- basic ----------
async Task Basic()
{
    var health = await http.GetAsync("/health");
    Console.WriteLine($"Health check: {(int)health.StatusCode}");
    var bad = await http.PostAsJsonAsync("/generate", new { prompt = "", max_tokens = 16 });
    Console.WriteLine($"Empty prompt: {(int)bad.StatusCode} " +
        (bad.StatusCode == HttpStatusCode.BadRequest ? "PASS" : "FAIL"));

    Console.WriteLine("\n--- 5 requests at the same time ---");
    var total = Stopwatch.StartNew();
    var results = await Task.WhenAll(Enumerable.Range(1, 5).Select(async i =>
    {
        var sw = Stopwatch.StartNew();
        var r = await Generate("What is MTBF? One sentence.");
        return (i, client: sw.Elapsed.TotalSeconds, r);
    }));
    foreach (var x in results.OrderBy(x => x.client))
        Console.WriteLine($"#{x.i}: total {x.client:F2}s | waited {x.r.queue_s}s | " +
            $"generated {x.r.infer_s}s | {x.r.tokens_per_s} tok/s");
    Console.WriteLine($"All done in: {total.Elapsed.TotalSeconds:F2}s");
}

// ---------- fairness ----------
async Task Fairness(int count, int gapMs)
{
    Console.WriteLine($"--- Fairness test: {count} requests, {gapMs} ms apart ---");
    var tasks = new List<Task<(int sent, GenResp r)>>();
    for (int i = 1; i <= count; i++)
    {
        int sent = i;
        tasks.Add(Task.Run(async () => (sent, await Generate($"Name one reliability metric. #{sent}", 32))));
        await Task.Delay(gapMs);
    }
    var results = await Task.WhenAll(tasks);

    var byArrive = results.OrderBy(x => x.r.arrive_no).ToList();
    var startRank = results.OrderBy(x => x.r.start_no)
        .Select((x, idx) => (x.sent, rank: idx + 1))
        .ToDictionary(t => t.sent, t => t.rank);

    int violations = 0;
    for (int k = 0; k < byArrive.Count; k++)
    {
        var (sent, r) = byArrive[k];
        int sr = startRank[sent];
        bool ok = sr == k + 1;
        if (!ok) violations++;
        Console.WriteLine($"sent #{sent} | arrived {k + 1} | served {sr} | " +
            $"waited {r.queue_s}s {(ok ? "" : "<-- OUT OF ORDER")}");
    }
    Console.WriteLine($"\nOut of order: {violations}/{count} -> {(violations == 0 ? "PASS" : "FAIL")}");
}

// ---------- soak ----------
async Task Soak(int minutes)
{
    SetThreadExecutionState(0x80000001); // stay awake (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    var health = await http.GetFromJsonAsync<HealthResp>("/health");
    var proc = Process.GetProcessById(health!.pid);
    string[] prompts = { "What is MTBF?", "Explain FMEA briefly.",
                         "What is a Weibull distribution?", "Define failure rate." };
    using var csv = new StreamWriter("soak.csv") { AutoFlush = true };
    csv.WriteLine("minute,requests,errors,avg_s,p95_s,max_s,tok_per_s,server_mem_mb");
    Console.WriteLine($"--- Soak test: {minutes} min, server PID {health.pid} ---");

    var end = DateTime.Now.AddMinutes(minutes);
    int minute = 0, n = 0;
    while (DateTime.Now < end)
    {
        minute++;
        var lat = new List<double>(); var tps = new List<double>(); int errors = 0;
        var minuteEnd = DateTime.Now.AddMinutes(1);
        while (DateTime.Now < minuteEnd)
        {
            var sw = Stopwatch.StartNew();
            try
            {
                var r = await Generate(prompts[n++ % prompts.Length]);
                lat.Add(sw.Elapsed.TotalSeconds);
                tps.Add(r.tokens_per_s);
                if (sw.Elapsed.TotalSeconds > 30)
                    Console.WriteLine($"  WARNING: one request took {sw.Elapsed.TotalSeconds:F0}s (sleep or freeze?)");
            }
            catch (Exception ex)
            {
                errors++;
                Console.WriteLine($"  ERROR: {ex.GetType().Name}: {ex.Message}");
                await Task.Delay(1000);   // do not spam a dead server
            }
        }

        string mem;
        if (proc.HasExited) mem = "SERVER DOWN";
        else { proc.Refresh(); mem = $"{proc.WorkingSet64 / 1048576.0:F0}"; }

        lat.Sort();
        double avg = lat.Count > 0 ? lat.Average() : 0;
        double p95 = lat.Count > 0 ? lat[(int)Math.Ceiling(lat.Count * 0.95) - 1] : 0;
        double max = lat.Count > 0 ? lat[^1] : 0;
        double tpsAvg = tps.Count > 0 ? tps.Average() : 0;

        Console.WriteLine($"[min {minute,3}] requests {lat.Count,3} | errors {errors} | " +
            $"avg {avg:F2}s | p95 {p95:F2}s | max {max:F2}s | {tpsAvg:F1} tok/s | memory {mem} MB");
        csv.WriteLine(FormattableString.Invariant(
            $"{minute},{lat.Count},{errors},{avg:F3},{p95:F3},{max:F3},{tpsAvg:F1},{mem}"));
    }
    SetThreadExecutionState(0x80000000); // allow sleep again
    Console.WriteLine("Done. Results saved to soak.csv");
}

// ---------- eval ----------
async Task Eval()
{
    var cases = System.Text.Json.JsonSerializer.Deserialize<EvalCase[]>(File.ReadAllText("eval_set.json"))!;
    int pass = 0;
    Console.WriteLine($"--- Eval: {cases.Length} questions ---");
    foreach (var c in cases)
    {
        var r = await Generate(c.q, 64, 0);
        var text = r.text.ToLowerInvariant();
        bool ok = c.must.All(k => k.Split('|').Any(alt => text.Contains(alt)));
        if (ok) pass++;
        Console.WriteLine($"{(ok ? "PASS" : "FAIL")} | {c.q}");
        if (!ok) Console.WriteLine($"       expected: {string.Join(", ", c.must)}\n       got: {r.text.Replace("\n", " ")}");
    }
    Console.WriteLine($"\nScore: {pass}/{cases.Length} ({100.0 * pass / cases.Length:F0}%)");
}

record GenResp(string text, double latency_s, double queue_s, double infer_s, int tokens,
               double tokens_per_s, string finish_reason, int arrive_no, int start_no);
record HealthResp(string status, int pid, int workers);
record EvalCase(string q, string[] must);