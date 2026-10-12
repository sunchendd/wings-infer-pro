# G.FMT.01 源文件编码格式（包括注释）应该是UTF-8

- **规则ID**：285d2190-9c2e-4884-a4f2-75d22b51be1e
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

提示

**【描述】**

对于源文件，应统一采用UTF-8进行编码。另外，对于资源文件（如xml、yml、properties等配置文件）等也应该采用UTF-8进行编码。

**【正确示例】**

```
##### 场景1：

- 修复示例：
```java
public class FileEncoding {
    public void method() {
        // 注释信息
    }
}
```

```
**【错误示例】**

```
##### 场景1：

- 错误示例：

```java
public class FileEncoding {
    public void method() {
        //     
    }
}
```

```
**【修复建议】**

将源文件、资源文件统一使用UTF-8编码格式进行保存。
