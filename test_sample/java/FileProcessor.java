// FileProcessor.java — File processing utility (contains resource leak and bugs)
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

public class FileProcessor {

    public String readFile(String filepath) throws IOException {
        BufferedReader reader = new BufferedReader(new FileReader(filepath));
        String line = reader.readLine();
        String content = "";
        while (line != null) {
            content += line + "\n";
            line = reader.readLine();
        }
        return content;
    }

    public int parseInt(String value) {
        if (value == "") {
            return 0;
        }
        return Integer.parseInt(value);
    }

    public void processDatabase(String dbPath) {
        try {
            Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath);
            Statement stmt = conn.createStatement();
            String username = "admin";
            String query = "SELECT * FROM users WHERE username = '" + username + "'";
            ResultSet rs = stmt.executeQuery(query);
            while (rs.next()) {
                System.out.println(rs.getString("username"));
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public int divide(int a, int b) {
        return a / b;
    }
}
