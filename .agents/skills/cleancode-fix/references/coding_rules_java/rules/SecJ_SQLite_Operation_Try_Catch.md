# SecJ_SQLite_Operation_Try_Catch

- **规则ID**：80c65b49-8b3d-4d46-9d73-f64eeac60cf3
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

在Java程序中针对SQLite数据库操作可能出现的问题。它主要关注在调用数据库操作时，可能出现数据库连接已关闭的情况，这可能由于多线程实现不当，导致了状态的改变。这种情况下会抛出java.lang.IllegalStateException异常。如果在特定位置不进行异常处理，这个异常会一层层上传，直到有代码捕获和处理它。这可能导致应用程序崩溃

**【正确示例】**

```
```java

public void test01Good(SQLiteDatabase database, String tableName) {

try {

// 【GOOD】数据库操作被包裹在try-catch块中，捕获了IllegalStateException异常。在catch块中，可以适当地处理异常，比如打印异常信息或者进行日志记录。这样即使出现异常，程序也能够继续执行，避免崩溃

Cursor cursor = database.query("sqlite_master", new String[]{"[sql]"},

"[type] = 'table' and name = ?", new String[]{tableName}, null, null, null);

// 处理查询结果

} catch (IllegalStateException e) {

// 处理连接已关闭的异常，可以进行日志记录或其他适当的处理

…

}

}

```

```
**【错误示例】**

```
```java

public void test01Bad(SQLiteDatabase database, String tableName) {

// 【不符合】没有对可能抛出的IllegalStateException异常进行任何处理。如果在数据库操作过程中发生异常，它将传播到调用该方法的位置，可能导致应用程序崩溃或不可预测的行为

Cursor cursor = database.query("sqlite_master", new String[]{"[sql]"},

"[type] = 'table' and name = ?", new String[]{tableName}, null, null, null);

// 没有对异常进行处理

// ...

}

```

```
**【修复建议】**

在进行数据库操作时，使用try-catch块捕获可能抛出的IllegalStateException异常，并在catch块中进行适当的处理
