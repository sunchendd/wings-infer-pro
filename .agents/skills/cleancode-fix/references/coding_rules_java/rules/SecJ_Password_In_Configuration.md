# SecJ_Password_In_Configuration

- **规则ID**：80eafaa3-206d-4c33-8d69-4fd9e195102f
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

当密码以明文形式或者含有password字样存储在应用程序的属性文件或其他配置文件中时，会发生 password management 漏洞。

**【正确示例】**

```
<?xml version="1.0" encoding="UTF-8" ?>
<configuration>
    <environments default="development">
        <environment id="development">
            <transactionManager type="JDBC"/>
            <dataSource type="POOLED">
                <property name="driver" value="com.mysql.jdbc.Driver"/>
                <property name="url" value="jdbc:mysql:///hwtestdb"/>
                <property name="username" value="root"/>
            </dataSource>
        </environment>
    </environments>
</configuration>

```
**【错误示例】**

```
<?xml version="1.0" encoding="UTF-8" ?>
<configuration>
    <environments default="development">
        <environment id="development">
            <transactionManager type="JDBC"/>
            <dataSource type="POOLED">
                <property name="driver" value="com.mysql.jdbc.Driver"/>
                <property name="url" value="jdbc:mysql:///hwtestdb"/>
                <property name="username" value="root"/>
                <!-- /* POTENTIAL FLAW: 在配置文件中存储明文密码，可能会危及系统安全。 */ -->
                <property name="password" value="root"/>
            </dataSource>
        </environment>
    </environments>
</configuration>

```
**【修复建议】**

不能采用明文的形式存储密码；不要使用password/passwd的等字样在应用程序的属性文件或其他配置文件中。
