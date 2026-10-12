# SecS_System_Information_Leak

- **规则ID**：81e3ed6d-0f0a-4c3d-a537-7b8ce2423cfb
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

在异常中不能输出口令、密钥和其他敏感信息，口令包括明文口令和密文口令，敏感信息包括系统等隐私信息。当敏感信息通过输出流或者日志功能流出程序时，就会发生信息泄漏

**【正确示例】**

```
```java
    public void bad() throws Throwable {
        {
            String data;
            data = ""; /* Initialize data */
            /* Read data from system information api */
            {
                data = Long.toString(Runtime.getRuntime().maxMemory());
            }
            if (!validData(data)) {
                return;
            }
            URL url = null;
            try {
                url = new URL("http://www.baidu.com");
                URLConnection connection = url.openConnection();
                /* 不符合: System Information Leak External */
                connection.setRequestProperty("xss", data);
            } catch (MalformedURLException e) {
                IO.writeLine(e.getMessage());
            } catch (IOException e) {
                IO.writeLine(e.getMessage());
            }

        }
    }

    private boolean validData(String data) {
        // 自定义校验函数，建议对data做白名单或者正则校验
    }
```

```
**【错误示例】**

```
```java
    public void bad() throws Throwable {
        {
            String data;
            data = ""; /* Initialize data */
            /* Read data from system information api */
            {
                data = Long.toString(Runtime.getRuntime().maxMemory());
            }
            URL url = null;
            try {
                url = new URL("http://www.baidu.com");
                URLConnection connection = url.openConnection();
                /* 不符合: System Information Leak External */
                connection.setRequestProperty("xss", data);
            } catch (MalformedURLException e) {
                IO.writeLine(e.getMessage());
            } catch (IOException e) {
                IO.writeLine(e.getMessage());
            }

        }
    }
```

```
**【修复建议】**

对于敏感信息建议采取以下方法：



- 不直接打印敏感信息。



- 若因为特殊原因必须要打印，对敏感信息进行脱敏处理，例如：用固定长度的星号（*）代替输出的敏感信息。

- 需要对敏感进行校验，比如白名单或者正则校验，使用valid开头的方法做校验。
