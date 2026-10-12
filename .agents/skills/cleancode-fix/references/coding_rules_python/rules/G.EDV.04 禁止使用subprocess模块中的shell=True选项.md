# G.EDV.04 禁止使用subprocess模块中的shell=True选项

- **规则ID**：55116517-8eec-4f6e-82ad-6fbe63b19644
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

subprocess模块帮助开发者执行外部命令和程序，为开发者带来便利的同时也带来了风险，该模块下多个接口（如call、check_call、Popen、check_output等）都可以传递shell参数。

shell=True这个参数的功能是Python解释器先运行一个shell环境，再用这个shell来执行Popen函数的第一个命令行字符串参数。

推荐调用子进程的方式是使用run()函数，对于其他需要使用到更高阶的用法的可以使用底层Popen()接口，需要注意的一点是使用Popen方式时，当stdout=PIPE或者stderr=PIPE时有可能会造成阻塞，除非调用Popen.communicate()才能解决。

**【正确示例】**

```
# 安全的做法是将shell参数置为False，前面的参数转成list列表，这样传入的参数里即使有注入指令也不会被解析执行，代码如下
import subprocess


def listdir_right(directory_):
    return subprocess.check_output(["notepad.exe", directory_], shell=False)


if __name__ == "__main__":
    _out = listdir_right("d:/abc.txt && calc.exe")

# 此时在Windows系统上执行上面的代码，你会发现系统记事本程序会尝试打开文件名由“d:/abc.txt && calc.exe”字符串组成的文件。

# 但是，以上正确示例的代码成为无风险代码还有个前提：

# 切记函数第一个参数列表的第一个元素不允许是bash，cmd，cmd.exe，/bin/sh，/usr/bin/expect等，只有满足了这个前提条件，参数显示设置shell=False参数才是有效防止命令注入的。遇到无法规避的情况，请联系安全SE备案解决。
import subprocess


def show_file(file_name):
    return subprocess.check_output(("cmd.exe", file_name), shell=False)


if __name__ == "__main__":
    _out = show_file("/c d:/abc.txt & echo bad_code >> d:/def.txt")

# 上面的代码在windows下以cmd.exe为主命令，后面的file_name整体作为cmd.exe的参数传入，内容中同样包含了危险的命令注入。虽然使用了命令序列化和shell=False参数，却仍然无法阻止命令注入。

```
**【错误示例】**

```
【反例1】
import subprocess


def run_cmd_wrong(_directory):
    return subprocess.check_output("notepad.exe %s" % _directory, shell=True)


if __name__ == "__main__":
    _out = run_cmd_wrong("d:/abc.txt && calc.exe")

# 此时执行脚本，你会发现脚本利用记事本打开了 d:/abc.txt 文件，接着也成功运行了计算器程序。

【反例2】演示第1个参数为什么不能是bash、cmd、cmd.exe、/bin/sh、 /usr/bin/expect 等系统命令，否则就相当于使用了shell=True参数。
expect_script = """
echo sssss22222 >> test_write_something.txt
echo sssss33333 >> test_write_something.txt
calc.exe
"""

# windows环境类似场景， 假设cmd.exe 是宿主程序，比如 /usr/bin/expect
# 传入交互的命令，如上面的多行写入
process = subprocess.run(["cmd.exe"], input=expect_script.encode("utf8"), shell=False, stdout=subprocess.PIPE)

# 宿主程序的标准输出
print(process.stdout)
执行上面的代码你会发现生成了文件“test_write_something.txt”，并且成功运行了计算器程序。

```
**【修复建议】**
