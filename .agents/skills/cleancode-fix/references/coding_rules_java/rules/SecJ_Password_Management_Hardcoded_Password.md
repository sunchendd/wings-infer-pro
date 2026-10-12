# SecJ_Password_Management_Hardcoded_Password

- **规则ID**：34c8ad59-8a2f-4b37-8aa0-1915118b98e5
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

当密码以明文形式存储在应用程序的属性文件或其他配置文件中时，会发生 password management 漏洞。

**【正确示例】**

```
package PasswordManagement.HardcodedPassword;

import com.huawei.IO;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class CWE259_PasswordManagement_HardcodedPassword_01 {
    public void good() {
        try {
            try (Connection connection = DriverManager.getConnection("127.1.1.1", "root", getPasswordByConfig())) {
                IO.writeLine(connection.getClientInfo().getProperty("value"));
            }
        } catch (SQLException e) {
            IO.writeLine(e.getMessage());
        }
    }
}

```
**【错误示例】**

```
package PasswordManagement.HardcodedPassword;

import com.huawei.IO;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class CWE259_PasswordManagement_HardcodedPassword_01 {
    public void bad() {
        try {
            /* POTENTIAL FLAW: Hardcoded Password */
            try (Connection connection = DriverManager.getConnection("127.1.1.1", "root", "pwd")) {
                IO.writeLine(connection.getClientInfo().getProperty("value"));
            }
        } catch (SQLException e) {
            IO.writeLine(e.getMessage());
        }
    }
}

```
**【修复建议】**

不能采用明文的形式存储密码。
