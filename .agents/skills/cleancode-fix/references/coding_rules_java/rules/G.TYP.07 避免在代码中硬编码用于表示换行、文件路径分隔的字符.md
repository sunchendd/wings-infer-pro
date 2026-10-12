# G.TYP.07 避免在代码中硬编码用于表示换行、文件路径分隔的字符

- **规则ID**：b1c70544-9cd6-44af-98c7-74db5d9caba9
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

回车换行符("\r"、"

")、文件路径分隔符("\"、"/")在不同操作系统下是有区别的。如果需要换行，尽量用PrintStream、PrintWriter的println()来代替在字符串中使用硬编码换行符，也可以使用**System.lineSeparator()**获取运行时环境的换行符。文件路径分割符可以使用java.io.File中的separator和pathSeparator静态字段。



工具检查场景:

-检查代码中使用换行（回车“\r”、换行“

”）

-检查代码中文件路径分隔（“\\”、“/”）的字符

**【正确示例】**

```
System.out.println("Hello,world!");
String filePath = path + File.separator + "temp.txt";

```
**【错误示例】**

```
System.out.print("Hello,world!
");
String filePath = path + "\\temp.txt";

```
**【修复建议】**

使用系统API获取回车换行符和文件路径分割符
