# G.EDV.01 禁止直接使用外部数据来拼接SQL语句

- **规则ID**：6390828f-21a6-4a27-b441-89f030b933ee
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

secBrella告警清理指导链接:http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&navid=NVI1000072710

SQL injection 错误在以下情况下发生：1）数据从一个不可信赖的数据源进入程序；2）数据用于动态地构造一个 SQL 查询。

**【正确示例】**

```
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper
        PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-mapper.dtd">

<mapper namespace="com.huawei.mybatis.IUserDao">
    <delete id="deleteUser" parameterType="com.huawei.pojo.User">
        delete from user where username like '%#{username}%'
    </delete>

    <delete id="deleteUserBySearch" parameterType="com.huawei.pojo.User">
        delete from user
        <where>
            <if test="address!=null">AND address = #{address}</if>
            <if test="username!=null">AND username like '%#{username}%'</if>
        </where>
    </delete>

</mapper>

```
**【错误示例】**

```
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper
        PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-mapper.dtd">

<mapper namespace="com.huawei.mybatis.IUserDao">
    <!-- /* POTENTIAL FLAW: 通过不可信来源的输入构建动态 SQL 指令，攻击者就能够修改指令的含义或者执行任意 SQL 命令。变量名称周围的 # 字符表示 MyBatis 将使用 userName 变量创建参数化查询。但是，MyBatis 还允许使用 $ 字符将变量直接连接到 SQL 指令，使其易受 SQL injection 攻击。 */ -->
    <delete id="deleteUser" parameterType="com.huawei.pojo.User">
        delete from user where username like '%${username}%'
    </delete>

    <delete id="deleteUserBySearch" parameterType="com.huawei.pojo.User">
        delete from user
        <where>
            <if test="address!=null">AND address = #{address}</if>
            <!-- /* POTENTIAL FLAW: 通过不可信来源的输入构建动态 SQL 指令，攻击者就能够修改指令的含义或者执行任意 SQL 命令。变量名称周围的 # 字符表示 MyBatis 将使用 userName 变量创建参数化查询。但是，MyBatis 还允许使用 $ 字符将变量直接连接到 SQL 指令，使其易受 SQL injection 攻击。 */ -->
            <if test="username!=null">AND username like '%${username}%'</if>
        </where>
    </delete>

</mapper>

```
**【修复建议】**

请查看告警清理指导：http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&amp&navid=NVI1000072714
