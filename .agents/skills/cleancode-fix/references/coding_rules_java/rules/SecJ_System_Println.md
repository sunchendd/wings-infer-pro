# SecJ_System_Println

- **规则ID**：11c89050-e159-4518-940f-7509d8542fbc
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏。

**【正确示例】**

```
```java

import org.slf4j.Logger;

import org.slf4j.LoggerFactory;

Logger logger = LoggerFactory.getLogger(Slf4jLogbackExample.class);



public void test01Good() {

/* 【GOOD】 使用日志模块 */

logger.debug("Entering test");

}



public void test02Good() {

/* 【GOOD】 使用日志模块 */

logger.error("Entering test");

}



```

```
**【错误示例】**

```
```java

Logger log = Logger.getLogger(CWE497_J_Rule_SystemPrintln_Bad.class.getName());



public void test01Bad() {

/* 【不符合】: 当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏 */

System.out.println("Entering test");

}



public void test02Bad() {

/* 【不符合】: 当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏 */

System.err.println("Entering test");

}



public void test03Bad() {

PrintStream out = System.out;

/* 【不符合】: 当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏 */

out.println("Entering test");

}



public void test04Bad() {

PrintStream err = System.err;

/* 【不符合】: 当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏 */

err.println("Entering test");

}

```

```
**【修复建议】**

不使用System.out或System.err输出任何信息，应该使用程序自带的日志模块



例外场景: 部分前端控制台输出，无法使用专有日志模块时，可以例外
