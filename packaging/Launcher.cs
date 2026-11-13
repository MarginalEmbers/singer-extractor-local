// Build with the Windows .NET Framework C# compiler; no Python is needed to show this window.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("哦，金金的音道分离")]
[assembly: System.Reflection.AssemblyVersion("0.5.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("0.5.0.0")]

internal static class Launcher
{
    internal const string Title = "哦，金金的音道分离";
    internal static readonly string Root = AppDomain.CurrentDomain.BaseDirectory;
    internal static string Runtime = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "JinjinAudio", "runtime-cu128-py311-v1");
    internal static string Data = Path.Combine(Root, "data");
    internal static string Python { get { return Path.Combine(Runtime, "venv", "Scripts", "python.exe"); } }
    internal static string LogFile { get { return Path.Combine(Data, "logs", "setup.log"); } }
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    internal static readonly object LogLock = new object();
    internal static Action<string> OnLog;
    internal static bool Settings;

    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        string report = null;
        try
        {
            string selfTest = null;
            bool installOnly = false;
            bool offline = false;
            Settings = Path.GetFileNameWithoutExtension(Application.ExecutablePath) == "检查运行环境";
            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--runtime-root": Runtime = Path.GetFullPath(args[++i]); break;
                    case "--data-dir": Data = Path.GetFullPath(args[++i]); break;
                    case "--check-only": report = Path.GetFullPath(args[++i]); break;
                    case "--self-test": selfTest = Path.GetFullPath(args[++i]); break;
                    case "--install-only": installOnly = true; break;
                    case "--offline": offline = true; break;
                    case "--settings": Settings = true; break;
                    default: throw new ArgumentException("不支持的参数：" + args[i]);
                }
            }
            Directory.CreateDirectory(Path.GetDirectoryName(LogFile));
            using (var mutex = new Mutex(false, "Local\\JinjinAudio-Environment-" + HashText(Runtime.ToLowerInvariant()).Substring(0, 16)))
            {
                bool acquired;
                try { acquired = mutex.WaitOne(0); }
                catch (AbandonedMutexException) { acquired = true; }
                if (!acquired) { MessageBox.Show("环境检查或软件已在运行，请切换到已有窗口。", Title); return 1; }
                try
                {
                    VerifyPackage();
                    if (installOnly) Install(false).GetAwaiter().GetResult();
                    if (report != null || installOnly)
                    {
                        var result = Check().GetAwaiter().GetResult();
                        if (report != null) File.WriteAllText(report, Json.Serialize(result), new UTF8Encoding(false));
                        return Flag(result, "runtime_ok") ? 0 : 2;
                    }
                    if (selfTest != null)
                    {
                        return Run(Python, new[] { "desktop_app.py", "--data-dir", Data, "--self-test", selfTest }.Concat(offline ? new[] { "--offline" } : new string[0]).ToArray(), false).GetAwaiter().GetResult();
                    }
                    Application.Run(new SetupWindow());
                }
                finally { mutex.ReleaseMutex(); }
            }
            return 0;
        }
        catch (Exception exc)
        {
            try { Log(exc.ToString()); } catch { }
            if (report != null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(report));
                File.WriteAllText(report, Json.Serialize(Missing(exc.Message)), new UTF8Encoding(false));
                return 1;
            }
            MessageBox.Show("未能启动。\n\n" + exc.Message + "\n\n请完整解压软件到可写文件夹。日志位置：\n" + LogFile, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    internal static string Quote(string value)
    {
        // CommandLineToArgvW quoting: preserve spaces, quotes and trailing backslashes.
        var output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { output.Append('\\', slashes * 2 + 1); output.Append(c); slashes = 0; continue; }
            output.Append('\\', slashes); slashes = 0; output.Append(c);
        }
        output.Append('\\', slashes * 2); output.Append('"');
        return output.ToString();
    }

    internal static void Log(string message)
    {
        if (String.IsNullOrWhiteSpace(message)) return;
        lock (LogLock)
        {
            if (File.Exists(LogFile) && new FileInfo(LogFile).Length > 4 * 1024 * 1024)
            {
                File.Copy(LogFile, LogFile + ".1", true);
                File.WriteAllText(LogFile, "");
            }
            File.AppendAllText(LogFile, DateTime.Now.ToString("s") + " " + message + Environment.NewLine, Encoding.UTF8);
        }
        if (OnLog != null) OnLog(message);
    }

    internal static async Task<int> Run(string executable, string[] args, bool cpu)
    {
        return await Task.Run(() =>
        {
            var start = new ProcessStartInfo(executable, String.Join(" ", args.Select(Quote))) {
                WorkingDirectory = Path.Combine(Root, "app"), UseShellExecute = false,
                CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            // Do not inherit developer Python or unrelated Qt/DLL search paths.
            foreach (string key in start.EnvironmentVariables.Keys.Cast<string>().ToArray())
                if (key.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase) || key.StartsWith("UV_", StringComparison.OrdinalIgnoreCase) || key.StartsWith("PIP_", StringComparison.OrdinalIgnoreCase) || key.StartsWith("QT_", StringComparison.OrdinalIgnoreCase) || key == "VIRTUAL_ENV")
                    start.EnvironmentVariables.Remove(key);
            start.EnvironmentVariables["PATH"] = Path.GetDirectoryName(Python) + ";" + Environment.SystemDirectory + ";" + Environment.GetEnvironmentVariable("SystemRoot");
            start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            start.EnvironmentVariables["PYTHONUTF8"] = "1";
            start.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            start.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = Path.Combine(Runtime, "python");
            start.EnvironmentVariables["UV_CACHE_DIR"] = Path.Combine(Runtime, "cache");
            start.EnvironmentVariables["UV_LINK_MODE"] = "hardlink";
            start.EnvironmentVariables["UV_HTTP_TIMEOUT"] = "120";
            if (cpu) start.EnvironmentVariables["CUDA_VISIBLE_DEVICES"] = "-1";
            using (var process = new Process { StartInfo = start })
            {
                process.OutputDataReceived += (sender, e) => { if (e.Data != null) Log(e.Data); };
                process.ErrorDataReceived += (sender, e) => { if (e.Data != null) Log(e.Data); };
                process.Start();
                process.BeginOutputReadLine(); process.BeginErrorReadLine();
                process.WaitForExit();
                return process.ExitCode;
            }
        });
    }

    internal static string HashText(string text)
    {
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-", "").ToLowerInvariant();
    }

    private static string HashFile(string file)
    {
        using (var stream = File.OpenRead(file))
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static void VerifyPackage()
    {
        string manifest = Path.Combine(Root, "package-files.json");
        if (!File.Exists(manifest) || HashFile(manifest) != BuildInfo.ManifestHash)
            throw new IOException("软件文件清单缺失或被修改。请重新下载并完整解压发布包。");
        var files = Json.Deserialize<Dictionary<string, string>>(File.ReadAllText(manifest, Encoding.UTF8));
        foreach (var item in files)
        {
            string path = Path.GetFullPath(Path.Combine(Root, item.Key));
            if (!path.StartsWith(Root, StringComparison.OrdinalIgnoreCase) || !File.Exists(path) || HashFile(path) != item.Value)
                throw new IOException("软件文件缺失或校验失败：" + item.Key + "。请重新下载并完整解压。");
        }
    }

    internal static bool Flag(Dictionary<string, object> report, string key)
    { return report.ContainsKey(key) && Convert.ToBoolean(report[key]); }

    private static Dictionary<string, object> Missing(string detail)
    {
        return new Dictionary<string, object> { { "runtime_ok", false }, { "cuda_ok", false }, { "models_ok", false },
            { "checks", new object[] { new Dictionary<string, object> { { "name", "运行环境" }, { "ok", false }, { "detail", detail }, { "action", "点击“安装运行环境”或“修复运行环境”。不需要手动配置 Python。" } } } } };
    }

    internal static async Task<Dictionary<string, object>> Check()
    {
        if (!File.Exists(Python)) return Missing("尚未安装软件专属的 Python 和 GPU 推理库。");
        string report = Path.Combine(Data, "logs", "environment.json");
        if (File.Exists(report)) File.Delete(report);
        try
        {
            int code = await Run(Python, new[] { "-m", "singer_extractor.environment", "--data-dir", Data, "--lock", Path.Combine(Root, "requirements-runtime.lock"), "--report", report }, false);
            if (File.Exists(report)) return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(report, Encoding.UTF8));
            return Missing("Python 无法完成检查（退出码 " + code + "）。运行文件可能损坏，详情见安装日志。");
        }
        catch (Exception exc) { Log(exc.ToString()); return Missing("无法运行 Python：" + exc.Message); }
    }

    internal static async Task Install(bool repair)
    {
        Directory.CreateDirectory(Runtime);
        var disk = new DriveInfo(Path.GetPathRoot(Runtime));
        if (disk.AvailableFreeSpace < 12L * 1024 * 1024 * 1024)
            throw new IOException("运行环境所在盘至少需要 12 GiB 可用空间（含安装缓存）。请腾出空间后重试。\n" + Runtime);
        string uv = Path.Combine(Root, "tools", "uv.exe");
        Log("步骤 1/3：准备独立 Python 3.11.16，不修改系统 Python 或 PATH。");
        if (await Run(uv, new[] { "--no-config", "--no-progress", "venv", Path.Combine(Runtime, "venv"), "--python", "3.11.16", "--managed-python", "--allow-existing" }, false) != 0)
            throw new IOException("Python 下载或创建失败。请检查网络能否访问 GitHub / Astral，查看日志后重试。");
        Log("步骤 2/3：安装 GPU 推理库，下载约 3 GB，较长时间没有新日志也可能仍在下载。");
        var gpu = new List<string> { "--no-config", "--no-progress", "pip", "install", "--python", Python, "--no-deps", "--only-binary", ":all:", "torch==2.7.1+cu128", "--index-url", "https://download.pytorch.org/whl/cu128" };
        if (repair) gpu.Add("--reinstall");
        if (await Run(uv, gpu.ToArray(), false) != 0)
            throw new IOException("GPU 运行库安装失败。请检查网络、剩余空间及 download.pytorch.org 的可访问性，再重试。");
        Log("步骤 3/3：安装音频和桌面界面依赖。");
        var dependencies = new List<string> { "--no-config", "--no-progress", "pip", "install", "--python", Python, "--no-deps", "--only-binary", ":all:", "-r", Path.Combine(Root, "requirements-ui.lock"), "--index-url", "https://pypi.org/simple" };
        if (repair) dependencies.Add("--reinstall");
        if (await Run(uv, dependencies.ToArray(), false) != 0)
            throw new IOException("界面或音频依赖安装失败。请检查网络能否访问 PyPI，查看日志后重试。");
        Log("安装完成，正在实际加载运行库并检查 GPU。缓存可供下次修复复用。");
    }
}

internal sealed class SetupWindow : Form
{
    private readonly Label summary = new Label();
    private readonly TextBox details = new TextBox();
    private readonly Button install = new Button();
    private readonly Button retry = new Button();
    private readonly Button start = new Button();
    private readonly ProgressBar progress = new ProgressBar();
    private bool busy;
    private bool runtimeReady;
    private bool cudaReady;
    private DateTime began;
    private readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();

    internal SetupWindow()
    {
        SuspendLayout();
        AutoScaleDimensions = new SizeF(96F, 96F);
        AutoScaleMode = AutoScaleMode.Dpi;
        Text = Launcher.Title + " · 环境检查";
        Font = new Font("Microsoft YaHei UI", 10F);
        ClientSize = new Size(900, 660); MinimumSize = new Size(860, 600);
        StartPosition = FormStartPosition.CenterScreen;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), ColumnCount = 1, RowCount = 6 };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 110));
        layout.Controls.Add(new Label { Text = Launcher.Title, AutoSize = true, Dock = DockStyle.Fill, Margin = new Padding(3, 0, 3, 16), Font = new Font(Font.FontFamily, 19F, FontStyle.Bold) });
        layout.Controls.Add(new Label { Text = "这是在线安装版。首次需下载约 3–4 GB 运行环境，进入软件后另准备约 919 MB 模型，请预留至少 12 GiB 空间。\n安装到：" + Launcher.Runtime + "\n完成后使用独立桌面窗口，无需打开浏览器或安装 CUDA Toolkit。", AutoSize = true, MaximumSize = new Size(820, 0), Dock = DockStyle.Fill, Margin = new Padding(3, 0, 3, 16) });
        summary.AutoSize = true; summary.MaximumSize = new Size(820, 0); summary.Margin = new Padding(3, 0, 3, 12); summary.Dock = DockStyle.Fill; summary.Text = "正在检查环境…"; layout.Controls.Add(summary);
        details.Multiline = true; details.ReadOnly = true; details.ScrollBars = ScrollBars.Vertical; details.Dock = DockStyle.Fill;
        layout.Controls.Add(details);
        progress.Dock = DockStyle.Fill; progress.Style = ProgressBarStyle.Marquee; layout.Controls.Add(progress);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(0, 8, 0, 0), WrapContents = true };
        install.Text = "安装运行环境";
        retry.Text = "重新检查";
        start.Text = "启动软件";
        var logs = new Button { Text = "查看日志" };
        var driver = new Button { Text = "NVIDIA 驱动" };
        var vc = new Button { Text = "VC++ 运行库" };
        foreach (var button in new[] { install, retry, start, logs, driver, vc })
        {
            button.AutoSize = true; button.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            button.MinimumSize = new Size(100, 38); button.Padding = new Padding(10, 6, 10, 6);
        }
        buttons.Controls.AddRange(new Control[] { install, retry, start, logs, driver, vc }); layout.Controls.Add(buttons); Controls.Add(layout);
        // Pin rows: hiding the progress bar must not move the buttons into its 28px row.
        for (int row = 0; row < layout.Controls.Count; row++)
            layout.SetCellPosition(layout.Controls[row], new TableLayoutPanelCellPosition(0, row));
        logs.Click += (s, e) => Process.Start(new ProcessStartInfo(Path.GetDirectoryName(Launcher.LogFile)) { UseShellExecute = true });
        driver.Click += (s, e) => Process.Start(new ProcessStartInfo("https://www.nvidia.com/Download/index.aspx") { UseShellExecute = true });
        vc.Click += (s, e) => Process.Start(new ProcessStartInfo("https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist") { UseShellExecute = true });
        Launcher.OnLog = message => { if (!IsDisposed && IsHandleCreated) BeginInvoke((Action)(() => { if (details.TextLength > 50000) details.Clear(); details.AppendText(message + Environment.NewLine); })); };
        timer.Interval = 1000;
        timer.Tick += (s, e) => { if (busy) summary.Text = "正在准备，请稍候… 已用 " + (DateTime.Now - began).ToString(@"mm\:ss") + "\n安装时请保持联网。详细步骤和错误会显示在下方。"; };
        install.Click += async (s, e) => await Work(async () => { await Launcher.Install(File.Exists(Launcher.Python)); await Inspect(false); });
        retry.Click += async (s, e) => await Work(async () => await Inspect(false));
        start.Click += async (s, e) => await Work(async () => await Launch());
        Shown += async (s, e) => await Work(async () => await Inspect(!Launcher.Settings));
        FormClosing += (s, e) => { if (busy) { e.Cancel = true; MessageBox.Show("当前正在检查、安装或运行软件。请等待完成；关闭主软件后启动器会自动退出。", Launcher.Title); } };
        ResumeLayout(true);
    }

    private async Task Work(Func<Task> action)
    {
        if (busy) return;
        busy = true; began = DateTime.Now; timer.Start();
        install.Enabled = retry.Enabled = start.Enabled = false; progress.Visible = true;
        try { await action(); }
        catch (Exception exc)
        {
            Launcher.Log(exc.ToString()); Show();
            summary.Text = "操作未完成：" + exc.Message;
        }
        finally
        {
            timer.Stop(); busy = false; progress.Visible = false;
            install.Text = File.Exists(Launcher.Python) ? "修复运行环境" : "安装运行环境";
            install.Enabled = retry.Enabled = true; start.Enabled = runtimeReady;
        }
    }

    private async Task Inspect(bool automatic)
    {
        var report = await Launcher.Check();
        runtimeReady = Launcher.Flag(report, "runtime_ok"); cudaReady = Launcher.Flag(report, "cuda_ok");
        details.Clear();
        foreach (Dictionary<string, object> check in (IEnumerable)report["checks"])
        {
            details.AppendText((Convert.ToBoolean(check["ok"]) ? "[通过] " : "[待处理] ") + check["name"] + "：" + check["detail"] + Environment.NewLine);
            if (!Convert.ToBoolean(check["ok"])) details.AppendText("    " + check["action"] + Environment.NewLine);
        }
        summary.Text = !runtimeReady ? "运行环境尚未就绪，请根据下方提示安装或修复。" : cudaReady ? "环境检查通过，可以使用 GPU 加速。" : "GPU 暂不可用。请更新驱动，或选择 CPU 继续（速度较慢）。";
        start.Text = cudaReady ? "启动软件（GPU）" : "使用 CPU 继续";
        if (runtimeReady && cudaReady && automatic) await Launch();
    }

    private async Task Launch()
    {
        Hide();
        int code = await Launcher.Run(Launcher.Python, new[] { "desktop_app.py", "--data-dir", Launcher.Data }, !cudaReady);
        if (code != 0)
        {
            Show(); Activate(); summary.Text = "主程序退出，错误码 " + code + "。请查看日志；运行库损坏时可点击修复。";
        }
        else { busy = false; Close(); }
    }
}
