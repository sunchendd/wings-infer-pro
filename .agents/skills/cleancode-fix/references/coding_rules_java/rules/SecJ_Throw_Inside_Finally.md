# SecJ_Throw_Inside_Finally

- **规则ID**：e788c9b3-299c-4ded-a905-68e4345ff286
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

块中的返回指令会导致从 try 块中抛出的异常丢失。

**【正确示例】**

```
public void test01Good(Connection conn) throws FileNotFoundException {
    FileInputStream fis = null;
    Statement stmt = null;
    try {
        stmt = conn.createStatement();
        fis = new FileInputStream("badFile.txt");
        ...
    } catch (FileNotFoundException fe) {
        log("File not found.");
        throw fe;
    } catch (SQLException se) {
        //handle error
    } finally {
        if (fis != null) {
            try {
                fis.close();
            } catch (IOException ie) {
                log(ie);
            }
        }
    
        if (stmt != null) {
            try {
                stmt.close();
            } catch (SQLException e) {
                log(e);
            }
        }
    }
}

```
**【错误示例】**

```
public void test01Bad() {
    try {
        return;
    } finally {
        /* POTENTIAL FLAW: Using a throw statement inside a finally block breaks the logical progression through the try-catch-finally. */
        throw new RuntimeException("Run Exception");
    }
}

```
**【修复建议】**
