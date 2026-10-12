# G.DCL.06 使用字面量风格的声明

- **规则ID**：0b9895b2-8d74-421c-8d33-c3636eeba995
- **更新时间**：2026-04-07 04:25:00

---

**【问题级别】**

一般

**【描述】**

SFTP链接未正常释放，大量session会话残留，内存缓慢泄漏直至溢出

**【正确示例】**

```
public void logout() {
    if (sftp != null) {
        if (sftp.isConnected()) {
            log.info("关闭sftp:{}", sftp);
            sftp.disconnect();              // 关闭channel对象
         }
        try {
            if (sftp.getSession() != null) {
                if (sftp.getSession().isConnected()) {
                    log.info("关闭sftp.getSession()");
                    sftp.getSession().disconnect();  // 关闭session对象
                }
            }
        } catch (Exception e) {
            log.error("关闭sftp.getSession()出现异常!", e);
        }
    }
}

```
**【错误示例】**

```
 public void logout() {
    if (sftp != null) {
        if (sftp.isConnected()) {
            log.info("关闭sftp");
            sftp.disconnect();   // 需要同时关闭channel对象和session对象
        }
    }
}

```
**【修复建议】**

在使用sftp连接时，在其使用完毕后，按先关闭sftp后关闭session的顺序关闭channel对象和session对象

另外可使用池化技术管理sftp连接，避免创建大量的sftp连接对象
